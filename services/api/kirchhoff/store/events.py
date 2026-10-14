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

    Parallel steps share one writer and pass `emit(..., step=...)`; `set_step` is for single-threaded callers."""

    def __init__(self, store: Store, run_path: str, phase: str, step: str, attempt: int = 1,
                 start_seq: int = 1, flush_interval_s: float = 0.25) -> None:
        self._store, self._run_path = store, run_path
        self._phase, self._step, self._attempt = phase, step, attempt
        self._seq = start_seq - 1
        self._pending: list[RunEvent] = []
        self._lock = threading.RLock()  # re-entrant: set_step flushes inside its critical section
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
        # One critical section: no concurrent default-step emit can land between the flush and the assignment.
        with self._lock:
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

    def _arm(self, delay_s: float) -> None:  # caller holds the lock
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
                rearm = (n <= MAX_FLUSH_RETRIES and not (self._fenced or self._closed)
                         and self._timer is None and bool(self._pending))
                if rearm:
                    self._arm(min(self._interval * 2 ** n, MAX_BACKOFF_S))
            if rearm:
                logger.warning("event writer trailing flush failed (%s); retry %d of %d",
                               type(exc).__name__, n, MAX_FLUSH_RETRIES)
            else:
                logger.error("event writer trailing flush failed (%s); pending events wait for the next "
                             "emit, flush or close", type(exc).__name__)

    def flush(self) -> None:
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
        with self._lock:
            self._closed = True  # set before flushing: a concurrent emit can no longer arm a timer
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        self.flush()

    def fence(self) -> None:
        with self._lock:
            self._fenced = True
            self._pending = []
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
