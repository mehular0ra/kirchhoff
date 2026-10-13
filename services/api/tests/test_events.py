import time

import pytest

from kirchhoff.store.events import EventWriter
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
