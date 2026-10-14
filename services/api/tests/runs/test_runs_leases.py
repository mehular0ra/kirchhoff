import pytest

from kirchhoff.runs.leases import (LIVE_RUNS_DOC, CapReached, acquire_lease, heartbeat, holds_lease, release_lease,
                                   run_path)
from kirchhoff.store.memory import MemoryStore


def _store_with_runs(*keys):
    s = MemoryStore()
    for uid, rid in keys:
        s.set_doc(run_path(uid, rid), {"id": rid, "status": "running", "lease": None})
    return s


def test_acquire_heartbeat_release_cycle():
    s = _store_with_runs(("u1", "r1"))
    assert acquire_lease(s, "u1", "r1", "w1", now=100.0, run_patch={"phase": "p1"}) == 1
    run = s.get_doc(run_path("u1", "r1"))
    assert run["phase"] == "p1" and holds_lease(run, "w1", 1)
    assert acquire_lease(s, "u1", "r1", "w2", now=110.0) is None  # live lease held by w1
    assert heartbeat(s, "u1", "r1", "w1", 1, now=150.0) is True
    assert release_lease(s, "u1", "r1", "w1", 1, {"status": "at_gate"}) is True
    run = s.get_doc(run_path("u1", "r1"))
    assert run["status"] == "at_gate" and run["lease"] == {"owner": None, "attempt": 1, "heartbeat_at": 0.0}
    assert acquire_lease(s, "u1", "r1", "w2", now=151.0) == 2  # attempt is monotonic across the run


def test_stale_lease_is_taken_over_and_old_owner_loses_heartbeat():
    s = _store_with_runs(("u1", "r1"))
    acquire_lease(s, "u1", "r1", "w1", now=100.0)
    assert acquire_lease(s, "u1", "r1", "w2", now=161.0) == 2
    assert heartbeat(s, "u1", "r1", "w1", 1, now=162.0) is False
    assert release_lease(s, "u1", "r1", "w1", 1, {"status": "done"}) is False
    assert s.get_doc(run_path("u1", "r1"))["status"] == "running"


def test_missing_run_cannot_be_leased():
    assert acquire_lease(MemoryStore(), "u1", "nope", "w1", now=1.0) is None


def test_global_cap_counts_only_live_leases():
    s = _store_with_runs(("a", "1"), ("b", "2"), ("c", "3"), ("d", "4"))
    for uid, rid in [("a", "1"), ("b", "2"), ("c", "3")]:
        assert acquire_lease(s, uid, rid, "w", now=100.0) == 1
    with pytest.raises(CapReached):
        acquire_lease(s, "d", "4", "w", now=101.0)
    assert s.get_doc(run_path("d", "4"))["lease"] is None  # nothing written
    release_lease(s, "a", "1", "w", 1, {"status": "at_gate"})
    assert acquire_lease(s, "d", "4", "w", now=102.0) == 1
    assert set(s.get_doc(LIVE_RUNS_DOC)["runs"]) == {"b__2", "c__3", "d__4"}
    assert acquire_lease(s, "a", "1", "w", now=200.0) == 2  # b, c, d are stale (> 60 s) by now


# --- Fix round 1: targeted regression coverage for the concurrency review ----------------------------


def test_cap_reached_leaves_live_runs_doc_untouched():
    s = _store_with_runs(("a", "1"), ("b", "2"), ("c", "3"), ("d", "4"))
    for uid, rid in [("a", "1"), ("b", "2"), ("c", "3")]:
        assert acquire_lease(s, uid, rid, "w", now=100.0) == 1
    before = s.get_doc(LIVE_RUNS_DOC)
    with pytest.raises(CapReached):
        acquire_lease(s, "d", "4", "w", now=101.0)
    assert s.get_doc(LIVE_RUNS_DOC) == before  # the transaction wrote nothing, not even a no-op write


def test_heartbeat_keeps_a_run_counted_past_the_original_60s_window():
    s = _store_with_runs(("a", "1"), ("b", "2"), ("c", "3"), ("d", "4"))
    for uid, rid in [("a", "1"), ("b", "2"), ("c", "3")]:
        acquire_lease(s, uid, rid, "w", now=0.0)
    # Without heartbeats, all three would be stale by now=65 (65 - 0 > STALE_S) and the cap
    # would not apply to "d". Heartbeating each at now=50 keeps them fresh (65 - 50 = 15 < STALE_S),
    # so the cap still blocks "d" at now=65.
    for uid, rid in [("a", "1"), ("b", "2"), ("c", "3")]:
        assert heartbeat(s, uid, rid, "w", 1, now=50.0) is True
    with pytest.raises(CapReached):
        acquire_lease(s, "d", "4", "w", now=65.0)


# --- Fix round 1: Minor 1, a transactional `expect` precondition ------------------------------------


def test_expect_true_lets_the_claim_through():
    s = _store_with_runs(("u1", "r1"))
    s.set_doc(run_path("u1", "r1"), {"id": "r1", "status": "at_gate", "gate": "plan", "lease": None})
    assert acquire_lease(s, "u1", "r1", "w1", now=100.0, expect=lambda run: run["status"] == "at_gate") == 1


def test_expect_false_aborts_with_no_write_at_all():
    s = _store_with_runs(("u1", "r1"))
    s.set_doc(run_path("u1", "r1"), {"id": "r1", "status": "done", "gate": None, "lease": None})
    before = s.get_doc(run_path("u1", "r1"))
    assert acquire_lease(s, "u1", "r1", "w1", now=100.0, expect=lambda run: run["status"] == "at_gate") is None
    assert s.get_doc(run_path("u1", "r1")) == before  # nothing written: not the run, not LIVE_RUNS_DOC


def test_expect_is_evaluated_on_the_actual_transaction_snapshot_not_a_stale_read():
    """The whole point of `expect`: it must see the run doc as it is INSIDE the transaction, not as it
    was read earlier by the caller -- otherwise it can't close a check-then-act race at all."""
    s = _store_with_runs(("u1", "r1"))
    s.set_doc(run_path("u1", "r1"), {"id": "r1", "status": "at_gate", "gate": "plan", "lease": None})
    # Simulate the run changing state *between* a caller's earlier read and this acquire_lease call.
    s.set_doc(run_path("u1", "r1"), {"id": "r1", "status": "expired", "gate": None, "lease": None})
    assert acquire_lease(s, "u1", "r1", "w1", now=100.0, expect=lambda run: run["status"] == "at_gate") is None
