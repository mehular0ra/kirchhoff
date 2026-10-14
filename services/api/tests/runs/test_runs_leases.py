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
