import threading
import time

import pytest

from kirchhoff.runs import orchestrator as orch
from kirchhoff.runs.leases import CapReached, LIVE_RUNS_DOC, run_path
from kirchhoff.runs.orchestrator import (GateExpired, WrongState, ensure_gate, resume_from_gate, resume_run,
                                        start_phase)
from kirchhoff.runs.steps import LeaseLost, ParkAtGate, PhaseOutcome, StepOutput, run_step

GATES = {"p1": "plan", "p2": "option", "p3": "review", "p4": None}


def dummy_phases(executed, fail_once=(), crash_once=(), park=None):
    failed: set[str] = set()

    def make(name):
        def run(ctx):
            for part in ("a", "b"):
                sid = f"{name}.{part}"

                def work(sid=sid):
                    executed.append(sid)
                    ctx.emit(sid, "system", "status", f"working {sid}")
                    if sid in fail_once and sid not in failed:
                        failed.add(sid)
                        raise RuntimeError("transient")
                    if sid in crash_once and sid not in failed:
                        failed.add(sid)
                        raise LeaseLost(sid)  # simulates the instance dying mid-step
                    return StepOutput(data={"ok": sid})

                run_step(ctx, sid, work)
            if park == name:
                raise ParkAtGate("option", "no qualifying option")
            ctx.metrics["tokens_in"] = 10.0
            return PhaseOutcome(gate=GATES[name])
        return run

    return {p: make(p) for p in GATES}


def _run(deps, rid):
    return deps.store.get_doc(run_path("u1", rid))


def _events(deps, rid):
    return deps.store.list_docs(f"{run_path('u1', rid)}/events")


def test_ask_mode_parks_at_every_gate_and_resumes(deps, make_run):
    executed: list[str] = []
    deps.phases = dummy_phases(executed)
    rid = make_run()
    assert start_phase(deps, "u1", rid, "p1") == 1
    run = _run(deps, rid)
    assert (run["status"], run["gate"], run["phase"]) == ("at_gate", "plan", "p1")
    assert run["lease"] == {"owner": None, "attempt": 1, "heartbeat_at": 0.0}
    assert "gate_entered_at" in run["metrics"] and run["metrics"]["tokens_in"] == 10.0
    for gate, nxt in (("plan", "option"), ("option", "review")):
        resume_from_gate(deps, "u1", rid, gate)
        assert (_run(deps, rid)["status"], _run(deps, rid)["gate"]) == ("at_gate", nxt)
    resume_from_gate(deps, "u1", rid, "review")
    run = _run(deps, rid)
    assert run["status"] == "done" and run["finished_at"] and run["lease"]["attempt"] == 4
    assert run["metrics"]["tokens_in"] == 40.0 and run["metrics"]["gate_wait_s"] >= 0
    # Deviation from the brief (documented in the Task 10 report): P2-R6 requires every orchestrator
    # call site to pass next_seq the worker's own (new) attempt, and next_seq's frozen Task 8 gap
    # logic (test_next_seq_jumps_past_a_stale_attempts_range_to_avoid_id_collision) gaps by SEQ_GAP on
    # *every* attempt increase, clean gate resume or not -- acquire_lease always bumps attempt by 1
    # whether the prior worker released cleanly or went stale, so next_seq cannot tell the two apart
    # from attempt numbers alone. Seqs are therefore strictly increasing, not contiguous, across a
    # gate resume (they stay contiguous *within* one attempt/phase).
    seqs = [e["seq"] for e in _events(deps, rid)]
    assert seqs[0] == 1 and all(b > a for a, b in zip(seqs, seqs[1:]))
    gates = [e["payload"] for e in _events(deps, rid) if e["kind"] == "gate"]
    assert gates == [{"gate": "plan", "auto": False}, {"gate": "option", "auto": False},
                     {"gate": "review", "auto": False}]


def test_auto_mode_runs_through_to_the_review_gate(deps, make_run):
    deps.phases = dummy_phases([])
    rid = make_run(autonomy="auto")
    start_phase(deps, "u1", rid, "p1")
    run = _run(deps, rid)
    assert (run["status"], run["gate"], run["phase"]) == ("at_gate", "review", "p3")
    assert [e["payload"]["auto"] for e in _events(deps, rid) if e["kind"] == "gate"] == [True, True, False]


def test_park_at_gate_is_forced_even_in_auto(deps, make_run):
    deps.phases = dummy_phases([], park="p2")
    rid = make_run(autonomy="auto")
    start_phase(deps, "u1", rid, "p1")
    run = _run(deps, rid)
    assert (run["status"], run["gate"], run["phase"]) == ("at_gate", "option", "p2")


def test_failure_then_resume_reruns_only_unfinished_steps(deps, make_run):
    executed: list[str] = []
    deps.phases = dummy_phases(executed, fail_once={"p1.b"})
    rid = make_run()
    start_phase(deps, "u1", rid, "p1")
    assert _run(deps, rid)["status"] == "failed"
    assert deps.store.get_doc(f"{run_path('u1', rid)}/steps/p1.failed")["status"] == "failed"
    assert resume_run(deps, "u1", rid) is True
    assert _run(deps, rid)["gate"] == "plan"
    assert executed == ["p1.a", "p1.b", "p1.b"]


def test_resume_after_dead_worker_takes_a_new_attempt(deps, make_run):
    executed: list[str] = []
    deps.phases = dummy_phases(executed, crash_once={"p1.b"})
    rid = make_run()
    start_phase(deps, "u1", rid, "p1")
    run = _run(deps, rid)
    assert run["status"] == "running" and run["lease"]["owner"] == deps.owner
    assert resume_run(deps, "u1", rid) is False  # lease still live
    deps.store.set_doc(run_path("u1", rid), {**run, "lease": {**run["lease"], "heartbeat_at": deps.clock() - 120}})
    assert resume_run(deps, "u1", rid) is True
    run = _run(deps, rid)
    assert run["gate"] == "plan" and run["lease"]["attempt"] == 2
    assert executed == ["p1.a", "p1.b", "p1.b"]
    step_b = deps.store.get_doc(f"{run_path('u1', rid)}/steps/p1.b")
    shown = [e for e in _events(deps, rid) if e["step"] == "p1.b" and e["attempt"] == step_b["attempt"]]
    assert len(shown) == 1  # UI rule: only the committing attempt's events


def test_gate_validation_and_expiry(deps, make_run):
    deps.phases = dummy_phases([])
    rid = make_run()
    start_phase(deps, "u1", rid, "p1")
    with pytest.raises(WrongState):
        ensure_gate(deps, "u1", rid, "option")
    run = _run(deps, rid)
    deps.store.set_doc(run_path("u1", rid), {**run, "metrics": {**run["metrics"],
                                                               "gate_entered_at": deps.clock() - 90_000}})
    with pytest.raises(GateExpired):
        resume_from_gate(deps, "u1", rid, "plan")
    assert _run(deps, rid)["status"] == "expired"


def test_global_cap_blocks_start(deps, make_run):
    deps.phases = dummy_phases([])
    now = deps.clock()
    deps.store.set_doc(LIVE_RUNS_DOC, {"runs": {"a__1": now, "b__2": now, "c__3": now}})
    with pytest.raises(CapReached):
        start_phase(deps, "u1", make_run(), "p1")


# ---------------------------------------------------------------------------
# Heartbeat self-fence (controller ruling on Task 8 concurrency reviews)
# ---------------------------------------------------------------------------


class FakeClock:
    """A controllable clock: `()` reads it, `advance(d)` moves it forward -- no real sleeping needed."""

    def __init__(self, t: float = 1_000_000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, d: float) -> None:
        self.t += d


def _wait_until(pred, timeout_s: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while not pred() and time.monotonic() < deadline:
        time.sleep(0.005)
    return pred()


def test_heartbeat_tick_self_fences_when_heartbeat_confirms_the_lease_is_lost(deps, make_run, monkeypatch):
    rid = make_run()
    clock = FakeClock()
    deps.clock = clock
    monkeypatch.setattr(orch, "heartbeat", lambda *a, **k: False)
    is_lost, _ = orch._heartbeat_tick(deps, "u1", rid, 1, clock())
    assert is_lost is True


def test_heartbeat_tick_does_not_self_fence_within_the_45s_grace_period(deps, make_run, monkeypatch):
    rid = make_run()
    clock = FakeClock()
    deps.clock = clock

    def boom(*a, **k):
        raise RuntimeError("firestore unavailable")

    monkeypatch.setattr(orch, "heartbeat", boom)
    last_ok = clock()
    clock.advance(orch.HEARTBEAT_STALE_S - 1)
    is_lost, last_ok = orch._heartbeat_tick(deps, "u1", rid, 1, last_ok)
    assert is_lost is False  # still inside the grace period, despite the failing heartbeat


def test_heartbeat_tick_self_fences_after_45s_of_failing_heartbeats(deps, make_run, monkeypatch):
    """If Firestore heartbeats keep failing (an exception, not a confirmed False), the worker cannot
    prove it still holds the lease; once the last confirmed heartbeat is older than 45 s it must
    self-fence and stop committing, rather than keep going on faith forever."""
    rid = make_run()
    clock = FakeClock()
    deps.clock = clock

    def boom(*a, **k):
        raise RuntimeError("firestore unavailable")

    monkeypatch.setattr(orch, "heartbeat", boom)
    last_ok = clock()
    clock.advance(orch.HEARTBEAT_STALE_S + 1)
    is_lost, _ = orch._heartbeat_tick(deps, "u1", rid, 1, last_ok)
    assert is_lost is True


def test_heartbeat_tick_resets_the_grace_period_on_a_confirmed_heartbeat(deps, make_run, monkeypatch):
    rid = make_run()
    clock = FakeClock()
    deps.clock = clock
    monkeypatch.setattr(orch, "heartbeat", lambda *a, **k: True)
    is_lost, last_ok = orch._heartbeat_tick(deps, "u1", rid, 1, clock())
    assert is_lost is False and last_ok == clock()


def test_heartbeat_loop_fences_the_current_writer_immediately_on_lost_lease(deps, make_run, monkeypatch):
    """The heartbeat loop must set the `lost` flag AND fence the phase writer itself, directly from the
    heartbeat thread, not only rely on the worker noticing on its next emit()."""
    rid = make_run()
    monkeypatch.setattr(orch, "heartbeat", lambda *a, **k: False)
    fenced = threading.Event()

    class FakeWriter:
        def fence(self) -> None:
            fenced.set()

    box = orch._WriterBox()
    box.set(FakeWriter())
    lost, stop = threading.Event(), threading.Event()
    deps.heartbeat_s = 0.01
    t = threading.Thread(target=orch._heartbeat_loop, args=(deps, "u1", rid, 1, lost, stop, box), daemon=True)
    t.start()
    try:
        assert _wait_until(lambda: lost.is_set() and fenced.is_set())
    finally:
        stop.set()
        t.join(2.0)
    assert not t.is_alive()


def test_heartbeat_loop_self_fences_once_the_grace_period_elapses_on_a_real_clock(deps, make_run, monkeypatch):
    """Even if heartbeat() never explicitly returns False (it just keeps raising, as a flaky Firestore
    would), the loop must still self-fence once HEARTBEAT_STALE_S has elapsed on deps.clock()."""
    rid = make_run()
    clock = FakeClock()
    deps.clock = clock
    deps.heartbeat_s = 0.01

    def boom(*a, **k):
        raise RuntimeError("firestore unavailable")

    monkeypatch.setattr(orch, "heartbeat", boom)
    fenced = threading.Event()

    class FakeWriter:
        def fence(self) -> None:
            fenced.set()

    box = orch._WriterBox()
    box.set(FakeWriter())
    lost, stop = threading.Event(), threading.Event()
    t = threading.Thread(target=orch._heartbeat_loop, args=(deps, "u1", rid, 1, lost, stop, box), daemon=True)
    t.start()
    try:
        time.sleep(0.05)
        assert not lost.is_set() and not fenced.is_set()  # still well inside the grace period
        clock.advance(orch.HEARTBEAT_STALE_S + 1)
        assert _wait_until(lambda: lost.is_set() and fenced.is_set())
    finally:
        stop.set()
        t.join(2.0)
    assert not t.is_alive()


def test_record_failure_does_not_emit_after_a_stale_takeover(deps, make_run):
    """`_record_failure` must check `holds_lease` and emit only if the lease is still held; it must not
    write a failure event once another attempt has already taken over."""
    rid = make_run()
    attempt = orch.acquire_lease(deps.store, "u1", rid, deps.owner, deps.clock(), {"phase": "p1"})
    run = _run(deps, rid)
    deps.store.set_doc(run_path("u1", rid), {**run, "lease": {"owner": "other", "attempt": attempt + 1,
                                                              "heartbeat_at": deps.clock()}})
    orch._record_failure(deps, "u1", rid, "p1", attempt, RuntimeError("boom"))
    assert _events(deps, rid) == []
    assert deps.store.get_doc(f"{run_path('u1', rid)}/steps/p1.failed") is None
