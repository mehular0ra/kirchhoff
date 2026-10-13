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
