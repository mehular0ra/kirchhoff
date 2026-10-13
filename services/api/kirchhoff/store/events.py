import threading
import time
from typing import Any

from kirchhoff.contracts import RunEvent

from . import Store


class EventWriter:
    """Assigns seq and writes RunEvents in batches (spec §11: ~250 ms batching, single writer per phase)."""

    def __init__(self, store: Store, run_path: str, phase: str, step: str, attempt: int = 1,
                 start_seq: int = 1, flush_interval_s: float = 0.25) -> None:
        self._store, self._run_path = store, run_path
        self._phase, self._step, self._attempt = phase, step, attempt
        self._seq = start_seq - 1
        self._pending: list[RunEvent] = []
        self._lock = threading.Lock()
        self._interval = flush_interval_s
        self._last_flush = time.monotonic()

    @property
    def last_seq(self) -> int:
        return self._seq

    def set_step(self, step: str) -> None:
        self.flush()
        self._step = step

    def emit(self, agent: str, kind: str, title: str, detail: str = "",
             payload: dict[str, Any] | None = None) -> RunEvent:
        with self._lock:
            self._seq += 1
            ev = RunEvent(seq=self._seq, phase=self._phase, step=self._step, attempt=self._attempt,
                          agent=agent, kind=kind, title=title, detail=detail, payload=payload or {},
                          ts=time.time())
            self._pending.append(ev)
            due = time.monotonic() - self._last_flush >= self._interval
        if due:
            self.flush()
        return ev

    def flush(self) -> None:
        with self._lock:
            items = [(f"{self._run_path}/events/{e.seq:06d}", e.model_dump()) for e in self._pending]
            self._pending = []
            self._last_flush = time.monotonic()
        if items:
            self._store.batch_set(items)

    def close(self) -> None:
        self.flush()
