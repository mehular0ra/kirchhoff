import logging
import threading
import time
from typing import Any

from kirchhoff.contracts import RunEvent

from . import Store
from .validate import firestore_safe_problems, json_size_bytes

logger = logging.getLogger("kirchhoff")

MAX_EVENT_BYTES = 10_000
MAX_FLUSH_RETRIES = 5
MAX_BACKOFF_S = 5.0


class EventWriter:
    """Assigns seq and writes RunEvents in batches (spec §11: ~250 ms batching, single writer per phase).

    Parallel steps share one writer and pass `emit(..., step=...)`; `set_step` is for single-threaded
    callers only. Never call `emit` (or any other method on this class) from inside a `Store.transact`
    `fn`: `fn` may be retried or run speculatively by the store, and `emit` has side effects (seq
    assignment, a Firestore write) that must not be duplicated or discarded by a retry.

    Locking: `_lock` guards in-memory state (`_pending`, `_step`, `_seq`, the flags, the timer handle)
    and is held only briefly. `_io` is held for the duration of an actual `batch_set` call, so at most
    one batch is ever in flight and a `flush()`/`close()` call only returns once its own batch (and any
    batch it had to wait behind) is durable or has definitively failed. `_io` is always acquired before
    `_lock`, never the reverse -- `flush()` takes `_io` first and then takes `_lock` only for the brief
    snapshot/requeue steps inside it, so other threads can still `emit` (which only needs `_lock`) while
    a batch is in flight.
    """

    def __init__(self, store: Store, run_path: str, phase: str, step: str, attempt: int = 1,
                 start_seq: int = 1, flush_interval_s: float = 0.25) -> None:
        self._store, self._run_path = store, run_path
        self._phase, self._step, self._attempt = phase, step, attempt
        self._seq = start_seq - 1
        self._pending: list[RunEvent] = []
        self._lock = threading.RLock()  # re-entrant: set_step flushes inside its critical section
        self._io = threading.RLock()  # serializes batch_set calls; always acquired before _lock
        self._interval = flush_interval_s
        self._last_flush = time.monotonic()
        self._timer: threading.Timer | None = None
        self._fenced = False
        self._closed = False
        self._retries = 0

    @property
    def last_seq(self) -> int:
        return self._seq

    def set_step(self, step: str) -> None:
        """Single-threaded callers only. Holds `_io` and `_lock` across the whole flush-then-assign
        critical section (including the commit of the flush), so no concurrent default-step `emit`
        can land between the flush and the assignment, and no concurrent flush can interleave with
        it either. Every event emitted by code that runs in parallel must pass `step=` explicitly
        instead of relying on this method."""
        with self._io, self._lock:
            self.flush()
            self._step = step

    def emit(self, agent: str, kind: str, title: str, detail: str = "",
             payload: dict[str, Any] | None = None, step: str | None = None) -> RunEvent:
        payload = payload or {}
        due = False
        with self._lock:
            if self._fenced:
                raise RuntimeError("event writer fenced")
            if self._closed:
                raise RuntimeError("event writer closed")
            problems = firestore_safe_problems(payload)
            if problems:
                raise ValueError(f"event payload is not Firestore-safe: {problems}")
            next_seq = self._seq + 1
            ev = RunEvent(seq=next_seq, phase=self._phase, step=step or self._step, attempt=self._attempt,
                          agent=agent, kind=kind, title=title, detail=detail, payload=payload,
                          ts=time.time())
            size = json_size_bytes(ev.model_dump())
            if size > MAX_EVENT_BYTES:
                raise ValueError(f"event payload too large: {size} bytes > {MAX_EVENT_BYTES} byte limit")
            self._seq = next_seq
            self._pending.append(ev)
            if self._interval == 0:
                due = True
            elif self._timer is None:
                self._arm(self._interval)
        if due:
            self.flush()
        return ev

    def _arm(self, delay_s: float) -> None:  # caller holds _lock (and possibly _io too)
        self._timer = threading.Timer(delay_s, self._timer_flush)
        self._timer.daemon = True
        self._timer.start()

    def _timer_flush(self) -> None:
        try:
            self.flush()
        except Exception as exc:
            with self._lock:
                self._retries += 1
                n = self._retries
                closed, fenced = self._closed, self._fenced
                already_armed = self._timer is not None  # someone else (e.g. a concurrent emit) armed one
                exhausted = n > MAX_FLUSH_RETRIES
                has_pending = bool(self._pending)
                rearm = has_pending and not closed and not fenced and not exhausted and not already_armed
                if rearm:
                    self._arm(min(self._interval * 2 ** n, MAX_BACKOFF_S))
            if closed:
                logger.error(
                    "event writer trailing flush failed (%s) after close(); events are lost or close() failed",
                    type(exc).__name__, exc_info=exc)
            elif fenced:
                logger.info(
                    "event writer trailing flush failed (%s) after fence(); pending events are dropped by design",
                    type(exc).__name__, exc_info=exc)
            elif not has_pending:
                pass  # a concurrent flush already drained _pending; nothing left to retry
            elif exhausted:
                logger.error(
                    "event writer trailing flush failed (%s); retry budget exhausted after %d attempts; "
                    "pending events wait for the next emit, flush or close",
                    type(exc).__name__, MAX_FLUSH_RETRIES, exc_info=exc)
            elif already_armed:
                logger.warning(
                    "event writer trailing flush failed (%s); another timer is already armed, a retry is scheduled",
                    type(exc).__name__, exc_info=exc)
            else:
                logger.warning(
                    "event writer trailing flush failed (%s); retry %d of %d scheduled",
                    type(exc).__name__, n, MAX_FLUSH_RETRIES, exc_info=exc)

    def flush(self) -> None:
        """Writes all pending events in one batch. The whole body -- snapshotting `_pending`, the
        `batch_set` call, requeueing on failure and resetting the retry counter -- runs under `_io`,
        so at most one batch is ever in flight: a concurrent `flush()`/`close()`/trailing-timer flush
        blocks here until this one finishes, and this call never returns while a batch it is
        responsible for is still in flight. `_lock` is only held for the brief snapshot/requeue steps,
        so `emit` is never blocked for the duration of a `batch_set` call."""
        with self._io:
            with self._lock:
                if self._fenced:
                    return
                if self._timer is not None:
                    self._timer.cancel()
                    self._timer = None
                items = [(f"{self._run_path}/events/{e.seq:06d}", e.model_dump()) for e in self._pending]
                pending_events = self._pending[:]  # Keep a copy to restore on failure
                self._pending = []
                self._last_flush = time.monotonic()
            if items:
                try:
                    self._store.batch_set(items)
                except Exception:
                    # Restore pending events at the front, preserving seq order
                    with self._lock:
                        self._pending = pending_events + self._pending
                    raise
                with self._lock:
                    self._retries = 0

    def close(self) -> None:
        """Idempotent. Sets the closed flag before flushing, so no concurrent `emit` can arm a new
        timer once `close()` has started, and raises `RuntimeError("event writer closed")` for any
        `emit` after that point. `close()` itself calls `flush()`, which (via `_io`) first waits for
        any batch already in flight (e.g. a trailing-timer flush) to finish, and then flushes whatever
        is still pending -- including events that in-flight batch had to requeue after failing. If that
        final flush also fails, `close()` raises (propagating `flush()`'s exception); the events are
        requeued in `_pending`, not durable yet, but never silently dropped -- calling `close()` again
        once the store recovers delivers them."""
        with self._lock:
            self._closed = True  # set before flushing: a concurrent emit can no longer arm a timer
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        self.flush()

    def fence(self) -> None:
        """Drops all pending events and blocks further emits. Takes only `_lock` (never `_io`), so a
        fence() call never blocks on I/O even if a batch is currently in flight."""
        with self._lock:
            self._fenced = True
            self._pending = []
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
