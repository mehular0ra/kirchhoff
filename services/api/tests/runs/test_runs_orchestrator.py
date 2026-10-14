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


# ---------------------------------------------------------------------------
# Fix round 1 (reviewer)
# ---------------------------------------------------------------------------


def test_failure_path_release_lease_error_does_not_crash_the_worker_thread(deps, make_run, monkeypatch):
    """Minor 3: a store error (e.g. a transient Firestore outage) in the failure-path release_lease call
    must not escape _worker as an uncaught exception -- it must be logged and swallowed, same as every
    other best-effort cleanup step the worker takes after a real step failure."""
    def boom(ctx):
        raise RuntimeError("engine exploded")

    deps.phases = {"p1": boom}
    rid = make_run()
    real_release = orch.release_lease

    def flaky_release(store, uid_, rid_, owner, attempt, patch):
        if patch.get("status") == "failed":
            raise RuntimeError("firestore unavailable")
        return real_release(store, uid_, rid_, owner, attempt, patch)

    monkeypatch.setattr(orch, "release_lease", flaky_release)
    start_phase(deps, "u1", rid, "p1")  # must not raise, even though the failure-path release blew up
    run = _run(deps, rid)
    assert run["status"] == "running"  # the release failed, so status could not flip to "failed"
    assert run["lease"]["owner"] == deps.owner  # the lease was never actually released either


def test_concurrent_start_phase_exactly_one_wins(deps, make_run):
    """Only one of several concurrent start_phase calls on the same run may win the lease; every other
    caller must raise LeaseBusy, never silently no-op or double-start a worker."""
    deps.phases = dummy_phases([])
    deps.spawn = lambda f: None  # don't actually run a worker; this test is only about the lease race
    rid = make_run()
    results: list = []
    lock = threading.Lock()
    barrier = threading.Barrier(6)

    def attempt():
        barrier.wait(5)
        try:
            r = start_phase(deps, "u1", rid, "p1")
        except orch.LeaseBusy:
            r = "busy"
        with lock:
            results.append(r)

    threads = [threading.Thread(target=attempt) for _ in range(6)]
    [t.start() for t in threads]
    [t.join(5) for t in threads]
    wins = [r for r in results if r != "busy"]
    assert wins == [1]  # exactly one caller won, with attempt 1
    assert results.count("busy") == 5


def test_metrics_accumulate_exactly_across_phases_and_gate_waits(deps, make_run):
    """Exact metrics bookkeeping with a fake clock (mirrors the reviewer's s10_metrics.py shape):
    tokens_in/out add up across phases, active_s is worker time only (excludes gate waits), and
    gate_wait_s accumulates across every gate resume rather than being overwritten by the latest one."""
    clock = FakeClock()
    deps.clock = clock

    def make(name, gate):
        def run(ctx):
            for part in ("a", "b"):
                sid = f"{name}.{part}"

                def work(sid=sid):
                    clock.advance(5.0)
                    return StepOutput(data={})
                run_step(ctx, sid, work)
            ctx.metrics["tokens_in"] = ctx.metrics.get("tokens_in", 0.0) + 7.0
            ctx.metrics["tokens_out"] = ctx.metrics.get("tokens_out", 0.0) + 3.0
            return PhaseOutcome(gate=gate)
        return run

    deps.phases = {"p1": make("p1", "plan"), "p2": make("p2", "option"), "p3": make("p3", "review"),
                  "p4": make("p4", None)}
    rid = make_run()

    start_phase(deps, "u1", rid, "p1")
    run = _run(deps, rid)
    assert run["metrics"]["active_s"] == 10.0
    assert run["metrics"]["tokens_in"] == 7.0 and run["metrics"]["tokens_out"] == 3.0

    clock.advance(100.0)
    resume_from_gate(deps, "u1", rid, "plan")
    run = _run(deps, rid)
    assert run["metrics"]["active_s"] == 20.0
    assert run["metrics"]["gate_wait_s"] == 100.0
    assert run["metrics"]["tokens_in"] == 14.0

    clock.advance(200.0)
    resume_from_gate(deps, "u1", rid, "option")
    run = _run(deps, rid)
    assert run["metrics"]["active_s"] == 30.0
    assert run["metrics"]["gate_wait_s"] == 300.0  # accumulated (100 + 200), never overwritten
    assert run["metrics"]["tokens_in"] == 21.0

    clock.advance(50.0)
    resume_from_gate(deps, "u1", rid, "review")
    run = _run(deps, rid)
    assert run["status"] == "done"
    assert run["metrics"]["active_s"] == 40.0
    assert run["metrics"]["gate_wait_s"] == 350.0
    assert run["metrics"]["tokens_in"] == 28.0 and run["metrics"]["tokens_out"] == 12.0


def test_patch_if_holder_raises_lease_lost_and_writes_nothing_under_a_new_holder(deps, make_run):
    """An Auto-mode worker advancing from one phase to the next (_patch_if_holder) must not patch
    `phase`/`metrics` once another attempt holds the lease -- it must raise LeaseLost and leave the run
    doc exactly as the new holder left it."""
    rid = make_run(autonomy="auto")
    attempt = orch.acquire_lease(deps.store, "u1", rid, deps.owner, deps.clock(), {"phase": "p1"})
    run = _run(deps, rid)
    deps.store.set_doc(run_path("u1", rid), {**run, "lease": {"owner": "other", "attempt": attempt + 1,
                                                              "heartbeat_at": deps.clock()}})
    with pytest.raises(LeaseLost):
        orch._patch_if_holder(deps, "u1", rid, attempt, {"phase": "p2", "metrics": {"x": 1.0}})
    after = _run(deps, rid)
    assert after["phase"] == "p1" and "x" not in (after.get("metrics") or {})


def test_auto_mode_worker_losing_the_lease_between_phases_does_not_patch_under_the_new_holder(deps, make_run):
    """End-to-end companion to the unit test above: an Auto-mode worker whose p1 completes, but whose
    lease is stolen before the advance-to-p2 patch lands, must raise LeaseLost out of _worker (caught,
    logged, no release -- "LeaseLost exits without writing") rather than clobber the new holder's run
    doc."""
    takeover_attempt = {}

    def p1(ctx):
        def a():
            return StepOutput(data={})
        run_step(ctx, "p1.a", a)

        def b():
            # Simulate a stale takeover landing right between p1's last step committing and the
            # Auto-mode advance-to-p2 patch (_patch_if_holder) for this same attempt.
            run = ctx.deps.store.get_doc(ctx.run_path)
            new_attempt = run["lease"]["attempt"] + 1
            ctx.deps.store.set_doc(ctx.run_path, {**run, "lease": {"owner": "other", "attempt": new_attempt,
                                                                    "heartbeat_at": ctx.deps.clock()}})
            takeover_attempt["v"] = new_attempt
            return StepOutput(data={})
        run_step(ctx, "p1.b", b)
        return PhaseOutcome(gate="plan")

    deps.phases = {"p1": p1}
    rid = make_run(autonomy="auto")
    start_phase(deps, "u1", rid, "p1")
    run = _run(deps, rid)
    # The new holder's lease/attempt must be untouched by the old worker's (failed) advance attempt.
    assert run["lease"]["owner"] == "other" and run["lease"]["attempt"] == takeover_attempt["v"]
    assert run["phase"] == "p1"  # never patched to "p2" under the new holder


def test_resume_run_on_an_at_gate_run_returns_false_and_leaves_the_gate_unchanged(deps, make_run):
    deps.phases = dummy_phases([])
    rid = make_run()
    start_phase(deps, "u1", rid, "p1")
    before = _run(deps, rid)
    assert before["status"] == "at_gate" and before["gate"] == "plan"
    assert resume_run(deps, "u1", rid) is False
    after = _run(deps, rid)
    assert after["status"] == "at_gate"
    assert after["gate"] == before["gate"]
    assert after["metrics"]["gate_entered_at"] == before["metrics"]["gate_entered_at"]


def test_resume_run_on_an_expired_at_gate_run_marks_it_expired_and_returns_false(deps, make_run):
    deps.phases = dummy_phases([])
    rid = make_run()
    start_phase(deps, "u1", rid, "p1")
    run = _run(deps, rid)
    deps.store.set_doc(run_path("u1", rid), {**run, "metrics": {**run["metrics"],
                                                               "gate_entered_at": deps.clock() - 90_000}})
    assert resume_run(deps, "u1", rid) is False
    after = _run(deps, rid)
    assert after["status"] == "expired" and after["gate"] is None and after["finished_at"]


def test_no_heartbeat_loop_threads_survive_after_the_worker_exits(deps, make_run):
    """Covers `finally: stop.set()` -- once a worker's phase parks at a gate (or finishes), its
    heartbeat thread must actually stop, not linger as a background thread."""
    from kirchhoff.runs.deps import thread_spawn
    deps.phases = dummy_phases([])
    deps.spawn = thread_spawn  # real background threads this time, not the conftest's synchronous spawn
    rid = make_run()
    before = threading.active_count()
    start_phase(deps, "u1", rid, "p1")
    assert _wait_until(lambda: (_run(deps, rid) or {}).get("status") == "at_gate")
    assert _wait_until(lambda: threading.active_count() <= before)


def test_gate_expiry_boundary_exactly_24h_is_valid_24h_plus_a_ms_is_expired(deps, make_run):
    deps.phases = dummy_phases([])
    rid = make_run()
    start_phase(deps, "u1", rid, "p1")
    entered = _run(deps, rid)["metrics"]["gate_entered_at"]

    deps.clock = FakeClock(entered + orch.GATE_TTL_S)  # exactly 24h: still valid
    run = ensure_gate(deps, "u1", rid, "plan")
    assert run["status"] == "at_gate"

    deps.clock = FakeClock(entered + orch.GATE_TTL_S + 0.001)  # 24h + 1ms: expired
    with pytest.raises(GateExpired):
        ensure_gate(deps, "u1", rid, "plan")
    after = _run(deps, rid)
    assert after["status"] == "expired" and after["gate"] is None and after["finished_at"]


# --- Minor 1 (fix round 1): a transactional gate claim closes the expiry check-then-act race (E1/E2) --


def _pause_on(store, predicate):
    """Pauses the FIRST store.transact() call whose read_paths matches `predicate`, in whichever thread
    reaches it first, until `go` is set. Mirrors the reviewer's harness `pause_on` helper."""
    reached, go, fired = threading.Event(), threading.Event(), []
    orig = store.transact

    def wrapped(read_paths, fn):
        if not fired and predicate(read_paths):
            fired.append(1)
            reached.set()
            assert go.wait(5), "probe: never released"
        return orig(read_paths, fn)
    store.transact = wrapped
    return reached, go, orig


def _side_deps(deps, owner, clock):
    from kirchhoff.runs.fakes import build_fake_deps
    d = build_fake_deps(deps.store, deps.scenarios_dir, seed_dir=deps.seed_dir, owner=owner, clock=clock,
                        heartbeat_s=3600.0, spawn=lambda f: f())
    d.phases = deps.phases
    return d


def test_e1_resume_from_gate_vs_concurrent_expiry(deps, make_run, monkeypatch):
    """E1: A's ensure_gate passes just under the 24h boundary, then A stalls right before its own
    acquire_lease transaction commits; B expires the run (just past the boundary) while A is stalled.
    A's transactional `expect` must see the now-expired run and abort -- it must never start p2 on an
    expired run -- and the precise, current exception (WrongState, since the run is "expired" now, not
    "at_gate") must surface instead of silently proceeding."""
    executed: list[str] = []
    deps.phases = dummy_phases(executed)
    rid = make_run()
    start_phase(deps, "u1", rid, "p1")
    entered = _run(deps, rid)["metrics"]["gate_entered_at"]

    a_deps = _side_deps(deps, "A", FakeClock(entered + orch.GATE_TTL_S - 0.1))
    b_deps = _side_deps(deps, "B", FakeClock(entered + orch.GATE_TTL_S + 0.1))
    reached, go, orig_transact = _pause_on(deps.store, lambda paths: paths == [run_path("u1", rid), LIVE_RUNS_DOC])
    results = {}

    def a_resume():
        try:
            results["A"] = resume_from_gate(a_deps, "u1", rid, "plan")
        except Exception as e:  # noqa: BLE001
            results["A"] = type(e).__name__

    t = threading.Thread(target=a_resume)
    t.start()
    assert reached.wait(5)
    with pytest.raises(GateExpired):
        ensure_gate(b_deps, "u1", rid, "plan")  # B expires the run while A is stalled mid-commit
    go.set()
    t.join(5)
    deps.store.transact = orig_transact
    assert results["A"] in ("WrongState", "GateExpired")
    run = _run(deps, rid)
    assert run["status"] == "expired" and run["gate"] is None
    assert not any(x.startswith("p2") for x in executed)  # p2 never ran on the expired run


def test_e2_resumed_run_is_never_reported_expired_once_its_worker_has_taken_over(deps, make_run):
    """E2: B reads the run as `at_gate` and past the boundary, and stalls right before its own (now
    conditional) expiry write; meanwhile A legitimately resumes (acquire_lease commits first) and its
    worker starts running p2. B's stalled expiry write must land as a no-op (the lease is now held),
    and ensure_gate must then report the CURRENT, accurate state (WrongState -- the run is "running"
    again) rather than a stale "expired" verdict for a run that has already moved on."""
    executed: list[str] = []
    entered_box = {}

    def make(name, gate, block):
        def run(ctx):
            for part in ("a", "b"):
                sid = f"{name}.{part}"

                def work(sid=sid, block=block):
                    executed.append(sid)
                    if block is not None:
                        entered, release = block
                        entered.set()
                        assert release.wait(5)
                    return StepOutput(data={})
                run_step(ctx, sid, work)
            return PhaseOutcome(gate=gate)
        return run

    rel = threading.Event()
    p2_entered = threading.Event()
    deps.phases = {"p1": make("p1", "plan", None), "p2": make("p2", "review", (p2_entered, rel)),
                  "p3": make("p3", None, None)}
    rid = make_run()
    start_phase(deps, "u1", rid, "p1")
    entered = _run(deps, rid)["metrics"]["gate_entered_at"]

    from kirchhoff.runs.deps import thread_spawn
    a_deps = _side_deps(deps, "A", FakeClock(entered + orch.GATE_TTL_S - 0.1))
    a_deps.spawn = thread_spawn  # A's worker must run in the background so this thread can keep driving
    b_deps = _side_deps(deps, "B", FakeClock(entered + orch.GATE_TTL_S + 0.1))
    reached, go, orig_transact = _pause_on(deps.store, lambda paths: paths == [run_path("u1", rid)])
    results = {}

    def b_ensure():
        try:
            ensure_gate(b_deps, "u1", rid, "plan")
            results["B"] = "ok"
        except GateExpired:
            results["B"] = "GateExpired"
        except WrongState:
            results["B"] = "WrongState"

    t = threading.Thread(target=b_ensure)
    t.start()
    assert reached.wait(5)  # B is stalled right inside its own (soon-to-be no-op) expiry write
    results["A"] = resume_from_gate(a_deps, "u1", rid, "plan")  # A resumes cleanly; its worker starts p2
    assert p2_entered.wait(5)  # A's worker is now inside p2, lease held by A
    go.set()  # let B's stalled expiry write proceed -- it must see the lease held and no-op
    t.join(5)
    deps.store.transact = orig_transact
    rel.set()  # let A's p2 finish
    assert _wait_until(lambda: (_run(deps, rid) or {}).get("status") == "at_gate")
    assert results["B"] == "WrongState"  # never told "expired" once A's worker had taken over
    run = _run(deps, rid)
    assert run["status"] != "expired"
