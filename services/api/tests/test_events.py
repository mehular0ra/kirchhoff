import threading
import time

import pytest

from kirchhoff.store.events import MAX_FLUSH_RETRIES, EventWriter
from kirchhoff.store.memory import MemoryStore


def test_event_writer_assigns_seq_and_batches():
    store = MemoryStore()
    w = EventWriter(store, "workspaces/u1/runs/r1", phase="p1", step="p1.intake", flush_interval_s=999)
    e1 = w.emit("intake", "status", "Reading tender")
    e2 = w.emit("intake", "message", "Found 18 requirements")
    assert (e1.seq, e2.seq) == (1, 2)
    assert store.list_docs("workspaces/u1/runs/r1/events") == []  # not flushed yet
    w.flush()
    docs = store.list_docs("workspaces/u1/runs/r1/events")
    assert [d["seq"] for d in docs] == [1, 2]
    assert docs[0]["step"] == "p1.intake" and docs[0]["attempt"] == 1


def test_event_writer_start_seq_continues_numbering():
    store = MemoryStore()
    w = EventWriter(store, "workspaces/u1/runs/r1", phase="p2", step="p2.x", start_seq=7, flush_interval_s=999)
    assert w.emit("layout", "status", "x").seq == 7
    w.close()
    assert store.get_doc("workspaces/u1/runs/r1/events/000007")["seq"] == 7


def test_event_writer_recovers_from_failed_flush():
    """Test that pending events are restored if batch_set fails, and a second flush succeeds."""
    class FailOnceThenSucceedStore:
        def __init__(self):
            self.docs = {}
            self.batch_set_count = 0

        def set_doc(self, path: str, data: dict) -> None:
            self.docs[path] = data

        def update_doc(self, path: str, data: dict) -> None:
            self.docs.setdefault(path, {}).update(data)

        def get_doc(self, path: str) -> dict | None:
            return self.docs.get(path)

        def batch_set(self, items: list[tuple[str, dict]]) -> None:
            self.batch_set_count += 1
            if self.batch_set_count == 1:
                raise RuntimeError("First batch_set fails")
            for path, data in items:
                self.docs[path] = data

        def list_docs(self, collection_path: str) -> list[dict]:
            prefix = collection_path.rstrip("/") + "/"
            depth = collection_path.count("/") + 2
            keys = sorted(k for k in self.docs if k.startswith(prefix) and k.count("/") + 1 == depth)
            return [self.docs[k] for k in keys]

    store = FailOnceThenSucceedStore()
    w = EventWriter(store, "workspaces/u1/runs/r1", phase="p1", step="p1.x", flush_interval_s=999)
    e1 = w.emit("system", "status", "Event 1")
    e2 = w.emit("system", "status", "Event 2")
    assert (e1.seq, e2.seq) == (1, 2)

    # First flush fails
    with pytest.raises(RuntimeError, match="First batch_set fails"):
        w.flush()

    # Events should still be in _pending
    assert w.last_seq == 2

    # Emit another event while pending from first flush
    e3 = w.emit("system", "status", "Event 3")
    assert e3.seq == 3

    # Second flush should succeed with all 3 events in order
    w.flush()
    docs = store.list_docs("workspaces/u1/runs/r1/events")
    assert [d["seq"] for d in docs] == [1, 2, 3]
    assert len(docs) == 3


def test_step_override_per_event_uses_shared_seq():
    store = MemoryStore()
    w = EventWriter(store, "workspaces/u1/runs/r1", phase="p1", step="p1.a", flush_interval_s=999)
    e1 = w.emit("system", "status", "first")
    e2 = w.emit("layout", "status", "second", step="p1.b")
    e3 = w.emit("system", "status", "third")
    assert [e1.step, e2.step, e3.step] == ["p1.a", "p1.b", "p1.a"]
    assert [e1.seq, e2.seq, e3.seq] == [1, 2, 3]


def test_unsafe_payload_raises_and_does_not_consume_seq():
    store = MemoryStore()
    w = EventWriter(store, "workspaces/u1/runs/r1", phase="p1", step="p1.a", flush_interval_s=999)
    with pytest.raises(ValueError):
        w.emit("system", "status", "bad", payload={"x": [[1, 2]]})
    e = w.emit("system", "status", "good")
    assert e.seq == 1


def test_oversized_payload_raises_and_does_not_consume_seq():
    store = MemoryStore()
    w = EventWriter(store, "workspaces/u1/runs/r1", phase="p1", step="p1.a", flush_interval_s=999)
    big_payload = {"blob": "x" * 20_000}
    with pytest.raises(ValueError):
        w.emit("system", "status", "bad", payload=big_payload)
    e = w.emit("system", "status", "good")
    assert e.seq == 1


def test_trailing_flush_writes_pending_event_without_another_emit():
    store = MemoryStore()
    w = EventWriter(store, "workspaces/u1/runs/r1", phase="p1", step="p1.a", flush_interval_s=0.05)
    w.emit("system", "status", "only event")
    assert store.list_docs("workspaces/u1/runs/r1/events") == []
    time.sleep(0.05 * 3)
    docs = store.list_docs("workspaces/u1/runs/r1/events")
    assert [d["seq"] for d in docs] == [1]
    w.close()


def test_fence_drops_pending_and_blocks_further_emits():
    store = MemoryStore()
    w = EventWriter(store, "workspaces/u1/runs/r1", phase="p1", step="p1.a", flush_interval_s=999)
    w.emit("system", "status", "first")
    w.fence()
    w.flush()  # should be a no-op, not raise
    assert store.list_docs("workspaces/u1/runs/r1/events") == []
    with pytest.raises(RuntimeError, match="fenced"):
        w.emit("system", "status", "second")


RP = "workspaces/u1/runs/r1"


class FlakyStore(MemoryStore):
    """Fails the first `fails` batch writes (Firestore unavailable), then behaves."""

    def __init__(self, fails: int) -> None:
        super().__init__()
        self.fails, self.calls = fails, 0

    def batch_set(self, items):
        self.calls += 1
        if self.fails:
            self.fails -= 1
            raise RuntimeError("firestore unavailable")
        super().batch_set(items)


def _wait_for(pred, timeout_s=2.0):
    deadline = time.monotonic() + timeout_s
    while not pred() and time.monotonic() < deadline:
        time.sleep(0.01)
    return pred()


def test_set_step_flush_and_assignment_are_one_critical_section():
    store = MemoryStore()
    w = EventWriter(store, RP, phase="p1", step="p1.a", flush_interval_s=999)
    w.emit("system", "status", "before")
    racing, real = [], store.batch_set

    def batch_set(items):  # runs inside set_step's flush; a concurrent default-step emit must wait for it
        t = threading.Thread(target=lambda: racing.append(w.emit("system", "status", "racing")))
        racing.append(t)
        t.start()
        t.join(0.1)
        real(items)

    store.batch_set = batch_set
    w.set_step("p1.b")
    store.batch_set = real
    racing[0].join(2.0)
    assert racing[1].step == "p1.b"
    w.close()
    assert [d["step"] for d in store.list_docs(f"{RP}/events")] == ["p1.a", "p1.b"]


def test_failed_trailing_flush_rearms_with_backoff():
    store = FlakyStore(fails=2)
    w = EventWriter(store, RP, phase="p1", step="p1.a", flush_interval_s=0.02)
    w.emit("system", "status", "only event")
    assert _wait_for(lambda: store.list_docs(f"{RP}/events"))
    assert [d["seq"] for d in store.list_docs(f"{RP}/events")] == [1] and store.calls == 3
    w.close()


def test_trailing_flush_gives_up_after_the_retry_budget_and_close_still_flushes():
    store = FlakyStore(fails=100)
    w = EventWriter(store, RP, phase="p1", step="p1.a", flush_interval_s=0.001)
    w.emit("system", "status", "only event")
    assert _wait_for(lambda: store.calls == 1 + MAX_FLUSH_RETRIES)
    time.sleep(0.2)
    assert store.calls == 1 + MAX_FLUSH_RETRIES  # no further timer is armed
    store.fails = 0
    w.close()
    assert [d["seq"] for d in store.list_docs(f"{RP}/events")] == [1]


def test_emit_after_close_raises_and_arms_no_timer():
    store = MemoryStore()
    w = EventWriter(store, RP, phase="p1", step="p1.a", flush_interval_s=0.01)
    w.emit("system", "status", "one")
    w.close()
    with pytest.raises(RuntimeError, match="closed"):
        w.emit("system", "status", "two")
    time.sleep(0.05)
    assert [d["seq"] for d in store.list_docs(f"{RP}/events")] == [1]
    w.close()  # idempotent


# --- Fix round 1: close()/flush() must wait for an in-flight batch, never return early ---------------


class SlowStore(MemoryStore):
    """A store whose batch_set takes `delay` seconds; optionally fails its first call."""

    def __init__(self, delay: float, fail_first: bool = False) -> None:
        super().__init__()
        self.delay, self.fail_first, self.calls = delay, fail_first, 0

    def batch_set(self, items):
        self.calls += 1
        n = self.calls
        time.sleep(self.delay)
        if self.fail_first and n == 1:
            raise RuntimeError("deadline exceeded")
        super().batch_set(items)


def test_close_waits_for_an_in_flight_timer_batch_before_returning():
    store = SlowStore(delay=0.1)
    w = EventWriter(store, RP, phase="p1", step="p1.a", flush_interval_s=0.02)
    for _ in range(3):
        w.emit("system", "status", "x")
    time.sleep(0.05)  # the trailing timer has fired; its 0.1 s batch_set is in flight
    w.close()  # must block until that batch is durable, not just snapshot newer (zero) events
    assert [d["seq"] for d in store.list_docs(f"{RP}/events")] == [1, 2, 3]


def test_close_after_a_failing_in_flight_batch_never_strands_events():
    """close() waits for the in-flight (failing) timer batch, then performs its own flush of
    whatever that batch requeued. Here the store recovers on the very next call, so close()'s own
    flush succeeds and the events become durable -- matching the documented contract: close()
    either makes the events durable itself or raises; they are never silently dropped."""
    store = SlowStore(delay=0.1, fail_first=True)
    w = EventWriter(store, RP, phase="p1", step="p1.a", flush_interval_s=0.02)
    for _ in range(3):
        w.emit("system", "status", "x")
    time.sleep(0.05)  # the trailing timer's batch (which will fail once) is in flight
    w.close()  # waits for that batch to fail and requeue, then flushes again itself
    assert [d["seq"] for d in store.list_docs(f"{RP}/events")] == [1, 2, 3]
    assert store.calls == 2  # the failing in-flight attempt, then close()'s own successful retry


def test_close_raises_and_does_not_strand_events_when_the_store_stays_down():
    """If close()'s own flush also fails (the store has not recovered), close() must raise rather
    than return having silently dropped the events; they stay queued (requeued by flush()) and a
    later close(), once the store recovers, delivers them."""

    class AlwaysFailStore(SlowStore):
        def batch_set(self, items):
            self.calls += 1
            time.sleep(self.delay)
            raise RuntimeError("still unavailable")

    store = AlwaysFailStore(delay=0.1)
    w = EventWriter(store, RP, phase="p1", step="p1.a", flush_interval_s=0.02)
    for _ in range(3):
        w.emit("system", "status", "x")
    time.sleep(0.05)  # the trailing timer's batch (which will fail) is in flight
    with pytest.raises(RuntimeError, match="still unavailable"):
        w.close()
    assert store.list_docs(f"{RP}/events") == []  # not silently stranded as "durable"
    # Once the store recovers, a later close() is not lost -- it delivers the requeued events.
    store.batch_set = MemoryStore.batch_set.__get__(store)
    w.close()
    assert [d["seq"] for d in store.list_docs(f"{RP}/events")] == [1, 2, 3]


def test_flush_blocks_until_a_concurrent_timer_batch_is_also_durable():
    store = SlowStore(delay=0.08)
    w = EventWriter(store, RP, phase="p1", step="p1.a", flush_interval_s=0.02)
    w.emit("system", "status", "one")
    time.sleep(0.04)  # the trailing timer fired; its batch_set for "one" is still in flight
    w.emit("system", "status", "two")  # queued after the in-flight batch's snapshot
    w.flush()  # must wait behind the in-flight batch, then flush "two", before returning
    assert [d["seq"] for d in store.list_docs(f"{RP}/events")] == [1, 2]
    w.close()


def test_backoff_grows_and_caps_at_5s_recorded_without_real_timers():
    store = FlakyStore(fails=100)
    w = EventWriter(store, RP, phase="p1", step="p1.a", flush_interval_s=1.0)
    delays: list[float] = []
    w._arm = lambda delay: delays.append(delay)  # record instead of arming a real threading.Timer
    w.emit("system", "status", "x")
    delays.clear()  # drop the initial arm from emit() itself; we only care about retry backoffs
    for _ in range(MAX_FLUSH_RETRIES + 1):
        w._timer_flush()  # drive the retry sequence directly; no sleeping
    assert delays == [2.0, 4.0, 5.0, 5.0, 5.0]  # 1*2**n for n=1..5, capped at MAX_BACKOFF_S


def test_a_trailing_flush_failing_after_close_logs_a_warning_not_an_error(caplog):
    """P2 final fix wave (Task 6 minor): after close() the events are requeued, not lost -- close() itself
    flushes (or raises) -- so a failed trailing flush is a WARNING, not a false ERROR alarm during judging."""
    import logging

    store = FlakyStore(fails=2)
    w = EventWriter(store, RP, phase="p1", step="p1.a", flush_interval_s=999)
    w.emit("system", "status", "x")
    with pytest.raises(RuntimeError, match="firestore unavailable"):
        w.close()  # close()'s own flush fails; the event stays queued
    with caplog.at_level(logging.WARNING, logger="kirchhoff"):
        w._timer_flush()  # a trailing flush that also fails after close()
    (rec,) = [r for r in caplog.records if "after close()" in r.getMessage()]
    assert rec.levelno == logging.WARNING and "close() will flush the requeued events" in rec.getMessage()
    w.close()  # the store has recovered: close() delivers the requeued event
    assert [d["seq"] for d in store.list_docs(f"{RP}/events")] == [1]
