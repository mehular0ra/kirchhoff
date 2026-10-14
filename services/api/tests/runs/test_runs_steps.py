import json
import uuid

import pytest

from kirchhoff.agents.runner import AgentSpec, ReplayRunner
from kirchhoff.contracts import RunRecord
from kirchhoff.runs.events import next_seq
from kirchhoff.runs.fakes import CheckedStore, build_fake_deps
from kirchhoff.runs.leases import acquire_lease, run_path
from kirchhoff.runs.outputs import load_outputs, pack_outputs
from kirchhoff.runs.steps import TXN_DOC_LIMIT, LeaseLost, PhaseContext, StepOutput, run_step
from kirchhoff.store.events import EventWriter


@pytest.fixture
def ctx(deps, make_run):
    rid = make_run()
    attempt = acquire_lease(deps.store, "u1", rid, deps.owner, deps.clock(), {"phase": "p2"})
    rp = run_path("u1", rid)
    events = EventWriter(deps.store, rp, phase="p2", step="p2.start", attempt=attempt,
                         start_seq=next_seq(deps.store, rp), flush_interval_s=999)  # run_step flushes
    return PhaseContext(deps, "u1", rid, "p2", attempt, events)


def _events(ctx):
    return ctx.deps.store.list_docs(f"{ctx.run_path}/events")


def test_commit_writes_outputs_and_done_marker_and_rerun_skips(ctx):
    calls = []

    def fn():
        calls.append(1)
        ctx.emit("p2.x", "layout", "status", "working")
        return StepOutput(data={"n": len(calls)}, docs=[("workspaces/u1/revisions/x-r1", {"id": "x-r1"})])

    assert run_step(ctx, "p2.x", fn) == {"n": 1}
    step = ctx.deps.store.get_doc(f"{ctx.run_path}/steps/p2.x")
    assert step["status"] == "done" and step["attempt"] == ctx.attempt
    assert step["outputs_ref"] == f"{ctx.run_path}/outputs/p2.x"
    assert ctx.deps.store.get_doc("workspaces/u1/revisions/x-r1") == {"id": "x-r1"}
    assert run_step(ctx, "p2.x", fn) == {"n": 1} and calls == [1]
    (ev,) = _events(ctx)
    assert (ev["step"], ev["attempt"], ev["seq"]) == ("p2.x", ctx.attempt, 1)


def test_stale_worker_cannot_commit_or_start(ctx):
    def takeover():
        run = ctx.deps.store.get_doc(ctx.run_path)
        ctx.deps.store.set_doc(ctx.run_path, {**run, "lease": {"owner": "other", "attempt": 9, "heartbeat_at": 1e12}})
        return StepOutput(data={"x": 1})

    with pytest.raises(LeaseLost):
        run_step(ctx, "p2.y", takeover)
    assert ctx.deps.store.get_doc(f"{ctx.run_path}/steps/p2.y")["status"] == "running"
    assert load_outputs(ctx.deps.store, ctx.deps.blobs, ctx.run_path, "p2.y") is None
    with pytest.raises(LeaseLost):
        run_step(ctx, "p2.z", lambda: StepOutput(data={}))


def test_failed_step_is_marked_failed(ctx):
    def boom():
        raise ValueError("engine exploded")

    with pytest.raises(ValueError):
        run_step(ctx, "p2.f", boom)
    assert ctx.deps.store.get_doc(f"{ctx.run_path}/steps/p2.f")["status"] == "failed"


def test_large_outputs_go_to_blob_storage(ctx):
    big = {"blob": "x" * 500_000}
    run_step(ctx, "p2.big", lambda: StepOutput(data=big))
    doc = ctx.deps.store.get_doc(f"{ctx.run_path}/outputs/p2.big")
    assert "blob" in doc and len(doc["sha256"]) == 64 and "json" not in doc
    assert load_outputs(ctx.deps.store, ctx.deps.blobs, ctx.run_path, "p2.big") == big


def test_emit_truncates_payload_and_narrate_sanitizes(ctx):
    def fn():
        ctx.emit("p2.n", "layout", "tool_result", "big", payload={"rows": ["x" * 100] * 200})
        ctx.narrate("p2.n", "power", "The drop is 2.16% on FA-01.", {"FA-01"}, "fix selection")
        ctx.narrate("p2.n", "power", "FA-01 fails R05.", {"FA-01"}, "fix selection")
        return StepOutput(data={})

    run_step(ctx, "p2.n", fn)
    big, dirty, clean = _events(ctx)
    assert big["payload"]["truncated"] is True
    assert dirty["title"] == "Power completed fix selection." and clean["title"] == "FA-01 fails R05."


def test_tool_wrapper_and_agent_fallback(ctx):
    ctx.deps.runner = ReplayRunner({"layout:p2.t": {"tool_calls": [{"name": "place_racks", "args": {"n": 2}}],
                                                    "text": "ok", "usage": {"in": 5, "out": 1}},
                                    "power:p2.t": {"raise": "vertex down"}})

    def place_racks(n: int = 0) -> dict:
        """Place racks."""
        return {"placed": n}

    def fn():
        res = ctx.agent(AgentSpec("layout", "x"), "p2.t", "go", tools=[ctx.tool("p2.t", "layout", place_racks)])
        assert res.tool_calls[0].result == {"placed": 2}
        assert ctx.agent(AgentSpec("power", "x"), "p2.t", "go") is None
        return StepOutput(data={})

    run_step(ctx, "p2.t", fn)
    kinds = [(e["agent"], e["kind"]) for e in _events(ctx)]
    assert kinds == [("layout", "tool_call"), ("layout", "tool_result"), ("power", "status")]
    assert ctx.metrics["tokens_in"] == 5


def test_next_seq_continues_from_highest_written(ctx):
    ctx.deps.store.set_doc(f"{ctx.run_path}/events/000041", {"seq": 41})
    assert next_seq(ctx.deps.store, ctx.run_path) == 42


def test_unsafe_step_docs_fail_the_step_before_commit(ctx):
    with pytest.raises(ValueError, match="Firestore-safe"):
        run_step(ctx, "p2.bad", lambda: StepOutput(data={}, docs=[("workspaces/u1/x/y", {"cols": [[0.0, 1.0]]})]))
    assert ctx.deps.store.get_doc(f"{ctx.run_path}/steps/p2.bad")["status"] == "failed"
    assert ctx.deps.store.get_doc("workspaces/u1/x/y") is None


def test_lost_lease_fences_the_writer(ctx):
    def fn():
        ctx.emit("p2.l", "layout", "status", "before")
        ctx.lease_lost.set()  # the heartbeat thread saw another owner
        ctx.emit("p2.l", "layout", "status", "after")
        return StepOutput(data={})

    with pytest.raises(LeaseLost):
        run_step(ctx, "p2.l", fn)
    ctx.events.close()
    assert _events(ctx) == []  # a stale worker writes no events


# ---------------------------------------------------------------------------
# Fix round 1 (concurrency review)
# ---------------------------------------------------------------------------


def test_next_seq_jumps_past_a_stale_attempts_range_to_avoid_id_collision(ctx):
    """I-1(a): event doc ids are events/{seq:06d}, shared across attempts. If the run has already moved
    to a newer attempt than the highest written event, a new writer must start far enough ahead that a
    stale worker's late flush (still numbering from the old attempt's range) can never collide."""
    ctx.deps.store.set_doc(f"{ctx.run_path}/events/000003", {"seq": 3, "attempt": ctx.attempt})
    run = ctx.deps.store.get_doc(ctx.run_path)
    ctx.deps.store.set_doc(ctx.run_path, {**run, "lease": {**run["lease"], "attempt": ctx.attempt + 1}})
    assert next_seq(ctx.deps.store, ctx.run_path) == 3 + 1 + 10_000


def test_next_seq_does_not_jump_when_the_attempt_is_unchanged(ctx):
    ctx.deps.store.set_doc(f"{ctx.run_path}/events/000005", {"seq": 5, "attempt": ctx.attempt})
    assert next_seq(ctx.deps.store, ctx.run_path) == 6


def test_stale_workers_pre_commit_flush_cannot_overwrite_the_committing_attempts_events(ctx):
    """I-1 end-to-end, mirroring the reviewer's race_two_workers.py: inside A's own fn, A flushes 1-3,
    holds 2 pending events, then B takes over (stale lease) and fully commits the SAME step with its
    own events; A's fn then returns and run_step's own pre-commit flush must not land on B's seq ids."""
    rid, attA = ctx.rid, ctx.attempt
    b = {}

    def fnA():
        for i in range(3):
            ctx.emit("p2.race", "layout", "status", f"A {i}")
        ctx.events.flush()
        ctx.emit("p2.race", "layout", "status", "A pending 1")
        ctx.emit("p2.race", "layout", "status", "A pending 2")
        # --- A stalls; its lease goes stale; B takes over and completes this same step ---
        now = ctx.deps.clock() + 61
        attB = acquire_lease(ctx.deps.store, "u1", rid, "other-owner", now)
        assert attB == attA + 1
        wB = EventWriter(ctx.deps.store, ctx.run_path, phase="p2", step="p2.race", attempt=attB,
                         start_seq=next_seq(ctx.deps.store, ctx.run_path), flush_interval_s=999)
        deps_b = build_fake_deps(ctx.deps.store, ctx.deps.scenarios_dir, seed_dir=ctx.deps.seed_dir,
                                 owner="other-owner", blobs=ctx.deps.blobs, clock=lambda: now, heartbeat_s=3600.0)
        ctxB = PhaseContext(deps_b, "u1", rid, "p2", attB, wB)

        def fnB():
            ctxB.emit("p2.race", "power", "status", "B one")
            ctxB.emit("p2.race", "power", "status", "B two")
            return StepOutput(data={"who": "B"})

        assert run_step(ctxB, "p2.race", fnB) == {"who": "B"}
        wB.close()
        b["attempt"] = attB
        b["events"] = {(e["seq"], e["title"]) for e in _events(ctx) if e["attempt"] == attB}
        # --- A wakes up and returns, straight into run_step's own pre-commit flush ---
        return StepOutput(data={"who": "A"})

    with pytest.raises(LeaseLost):
        run_step(ctx, "p2.race", fnA)

    assert {t for _, t in b["events"]} == {"B one", "B two"}
    # B's committed events must still be exactly {"B one", "B two"}: A's late flush did not land on the
    # same seq ids and overwrite them.
    still_there = {(seq, t) for seq, t in b["events"]
                   if any(e["seq"] == seq and e["title"] == t for e in _events(ctx))}
    assert still_there == b["events"]
    step = ctx.deps.store.get_doc(f"{ctx.run_path}/steps/p2.race")
    assert step["attempt"] == b["attempt"] and step["status"] == "done"


def test_begin_rejects_a_takeover_via_the_transaction_not_the_early_guard(ctx):
    """I-3: a fresh ctx (lease_lost never set) whose underlying lease was stolen must be rejected by
    begin's holds_lease check inside the transaction, not by the (vacuous, already-true) early guard."""
    assert not ctx.lease_lost.is_set()
    run = ctx.deps.store.get_doc(ctx.run_path)
    ctx.deps.store.set_doc(ctx.run_path, {**run, "lease": {"owner": "other", "attempt": 99, "heartbeat_at": 1e12}})

    with pytest.raises(LeaseLost):
        run_step(ctx, "p2.begin-lost", lambda: StepOutput(data={}))

    assert ctx.lease_lost.is_set()  # fenced as a side effect of begin losing the lease
    assert ctx.deps.store.get_doc(f"{ctx.run_path}/steps/p2.begin-lost") is None
    with pytest.raises(RuntimeError, match="fenced"):
        ctx.events.emit("layout", "status", "after fence")


def test_writer_is_fenced_after_a_commit_lost(ctx):
    def takeover():
        run = ctx.deps.store.get_doc(ctx.run_path)
        ctx.deps.store.set_doc(ctx.run_path, {**run, "lease": {"owner": "other", "attempt": 9, "heartbeat_at": 1e12}})
        return StepOutput(data={"x": 1})

    with pytest.raises(LeaseLost):
        run_step(ctx, "p2.commit-lost", takeover)
    with pytest.raises(RuntimeError, match="fenced"):
        ctx.events.emit("layout", "status", "after fence")


def test_events_flush_happens_before_the_commit_transaction(scen_dir, tmp_path):
    rid = uuid.uuid4().hex[:12]
    rp = run_path("u1", rid)

    class FlushAssertStore(CheckedStore):
        def __init__(self) -> None:
            super().__init__()
            self.commit_saw_events = False

        def transact(self, read_paths, fn):
            if read_paths == [rp]:  # the commit transaction reads only the run doc
                self.commit_saw_events = bool(self.list_docs(f"{rp}/events"))
            return super().transact(read_paths, fn)

    store = FlushAssertStore()
    deps = build_fake_deps(store, scen_dir, seed_dir=tmp_path, spawn=lambda f: f(), heartbeat_s=3600.0)
    rec = RunRecord(id=rid, project_id="hall-b", status="running", autonomy="ask", phase="p2",
                    started_at=deps.clock())
    store.set_doc(f"workspaces/u1/runs/{rid}", rec.model_dump(mode="json"))
    attempt = acquire_lease(store, "u1", rid, deps.owner, deps.clock())
    events = EventWriter(store, rp, phase="p2", step="p2.flush", attempt=attempt, start_seq=next_seq(store, rp),
                         flush_interval_s=999)
    ctx = PhaseContext(deps, "u1", rid, "p2", attempt, events)

    def fn():
        ctx.emit("p2.flush", "layout", "status", "working")
        return StepOutput(data={})

    run_step(ctx, "p2.flush", fn)
    assert store.commit_saw_events is True


def test_failed_step_without_the_lease_raises_lease_lost_and_fences(ctx):
    """I-1(c)/M-6: if the lease is already gone by the time the step's function fails, the failed-path
    write (which also checks holds_lease) must not silently mark 'failed' under a lease nobody holds --
    it must surface as LeaseLost and fence the writer, same as the begin/commit paths."""
    def boom():
        run = ctx.deps.store.get_doc(ctx.run_path)
        ctx.deps.store.set_doc(ctx.run_path, {**run, "lease": {"owner": "other", "attempt": 9, "heartbeat_at": 1e12}})
        raise ValueError("boom")

    with pytest.raises(LeaseLost):
        run_step(ctx, "p2.fail-no-lease", boom)
    assert ctx.lease_lost.is_set()
    step = ctx.deps.store.get_doc(f"{ctx.run_path}/steps/p2.fail-no-lease")
    assert step["status"] == "running"  # nobody held the lease to flip it to "failed"
    with pytest.raises(RuntimeError, match="fenced"):
        ctx.events.emit("layout", "status", "after fence")


def test_content_addressed_blob_path_and_tamper_detection(ctx):
    """I-2: the blob path is content-addressed (sha prefix), and load_outputs verifies the digest."""
    big = {"blob": "x" * 500_000}
    run_step(ctx, "p2.blob", lambda: StepOutput(data=big))
    doc = ctx.deps.store.get_doc(f"{ctx.run_path}/outputs/p2.blob")
    assert doc["blob"] == f"{ctx.run_path}/outputs/p2.blob.{doc['sha256'][:16]}.json"

    ctx.deps.blobs.put(doc["blob"], b'{"blob":"tampered"}', "application/json")
    with pytest.raises(ValueError, match="sha256"):
        load_outputs(ctx.deps.store, ctx.deps.blobs, ctx.run_path, "p2.blob")


def test_stale_workers_blob_write_cannot_affect_the_committed_blob(ctx):
    """I-2: a stale worker's late pack_outputs call for the same step_id, with different data, must land
    on a different (content-addressed) path and never overwrite what the committing attempt already wrote."""
    big_b = {"who": "B", "pad": "b" * 500_000}
    run_step(ctx, "p2.stale-blob", lambda: StepOutput(data=big_b))
    doc_b = ctx.deps.store.get_doc(f"{ctx.run_path}/outputs/p2.stale-blob")

    big_a = {"who": "A", "pad": "a" * 500_000}
    _, out_a = pack_outputs(ctx.deps.blobs, ctx.run_path, "p2.stale-blob", big_a)  # a stale worker's late write
    assert out_a["blob"] != doc_b["blob"]
    assert load_outputs(ctx.deps.store, ctx.deps.blobs, ctx.run_path, "p2.stale-blob") == big_b


def test_large_title_and_text_stay_under_the_event_cap(ctx, firestore_safe):
    """M-1: title and detail are clipped and the whole serialized event, not just the payload, is kept
    under the EventWriter's 10 KB cap."""
    def fn():
        ctx.emit("p2.cap", "layout", "tool_result", "t" * 900, payload={"rows": "x" * 8980})
        ctx.narrate("p2.cap", "power", "word " * 2500, set(), "x")
        ctx.ledger("p2.cap", "power", "did", "w" * 5000)
        return StepOutput(data={})

    run_step(ctx, "p2.cap", fn)
    events = _events(ctx)
    assert len(events) == 3
    for ev in events:
        assert len(json.dumps(ev, separators=(",", ":"), ensure_ascii=False).encode()) < 10_000
    firestore_safe(ctx.deps.store)


def test_failure_after_fn_marks_the_step_failed_and_reraises(ctx):
    """M-3: a failure after fn() returns -- non-JSON-serializable outputs reaching pack_outputs -- must
    still mark the step failed (lease held) and re-raise, not leave the step stuck 'running' forever."""
    class NotJSON:
        pass

    def fn():
        return StepOutput(data={"bad": NotJSON()})

    with pytest.raises(TypeError):
        run_step(ctx, "p2.badout", fn)
    assert ctx.deps.store.get_doc(f"{ctx.run_path}/steps/p2.badout")["status"] == "failed"


def test_flush_failure_after_fn_marks_the_step_failed(ctx):
    """M-3: a flush error (e.g. a transient Firestore failure) after fn() must also mark the step failed."""
    def broken_flush():
        raise RuntimeError("firestore 503")

    ctx.events.flush = broken_flush

    def fn():
        return StepOutput(data={})

    with pytest.raises(RuntimeError):
        run_step(ctx, "p2.flushfail", fn)
    assert ctx.deps.store.get_doc(f"{ctx.run_path}/steps/p2.flushfail")["status"] == "failed"


def test_more_than_400_docs_raises_before_any_write(ctx):
    """M-4: a StepOutput with more than the transactional doc limit must raise before anything is
    written -- no unleased bulk batch_set path."""
    docs = [(f"workspaces/u1/x/d{i}", {"i": i}) for i in range(TXN_DOC_LIMIT + 1)]

    def fn():
        return StepOutput(data={}, docs=docs)

    with pytest.raises(ValueError, match="limit"):
        run_step(ctx, "p2.toomany", fn)
    step = ctx.deps.store.get_doc(f"{ctx.run_path}/steps/p2.toomany")
    assert step["status"] == "failed"
    assert ctx.deps.store.get_doc("workspaces/u1/x/d0") is None
    assert load_outputs(ctx.deps.store, ctx.deps.blobs, ctx.run_path, "p2.toomany") is None
