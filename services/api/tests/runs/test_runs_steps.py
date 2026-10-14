import pytest

from kirchhoff.agents.runner import AgentSpec, ReplayRunner
from kirchhoff.runs.events import next_seq
from kirchhoff.runs.leases import acquire_lease, run_path
from kirchhoff.runs.outputs import load_outputs
from kirchhoff.runs.steps import LeaseLost, PhaseContext, StepOutput, run_step
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
