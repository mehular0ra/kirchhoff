import pytest

from kirchhoff.contracts import DesignBrief
from kirchhoff.runs.fakes import FakeEngine
from kirchhoff.runs.leases import run_path
from kirchhoff.runs.orchestrator import resume_from_gate, resume_run, start_phase
from kirchhoff.runs.outputs import load_outputs
from kirchhoff.runs.phase1 import run_p1
from kirchhoff.runs.phase2 import run_p2
from kirchhoff.runs.policy import PLAN_TEMPLATE
from kirchhoff.runs.steps import PhaseOutcome


def review_stub(ctx):
    return PhaseOutcome(gate="review")


@pytest.fixture
def p12(deps):
    deps.phases = {"p1": run_p1, "p2": run_p2, "p3": review_stub}
    return deps


def _run(d, rid):
    return d.store.get_doc(run_path("u1", rid))


def _events(d, rid):
    return d.store.list_docs(f"{run_path('u1', rid)}/events")


def _out(d, rid, step):
    return load_outputs(d.store, d.blobs, run_path("u1", rid), step)


def test_p1_reaches_plan_gate_with_a_verified_brief(p12, make_run):
    rid = make_run()
    start_phase(p12, "u1", rid, "p1")
    run = _run(p12, rid)
    assert (run["status"], run["gate"]) == ("at_gate", "plan")
    assert [p["id"] for p in run["plan"]] == [sid for sid, _, _ in PLAN_TEMPLATE]
    (q,) = run["open_questions"]
    assert q["id"] == "Q-redundancy" and q["resolution"] is None and q["default_resolution"] == "2N"
    brief = DesignBrief.model_validate(_out(p12, rid, "p1.intake")["brief"])
    assert sum(r.verified for r in brief.requirements) == 7 and brief.drawing_check["agrees"] is True
    assert brief.intake_score["recall"] == 7 / 32 and brief.intake_score["precision"] == 1.0
    titles = [e["title"] for e in _events(p12, rid)]
    assert "7/8 quotes verified" in titles and "Drawing read · DXF agrees" in titles
    assert {"tool_result", "artifact", "plan", "gate", "message"} <= {e["kind"] for e in _events(p12, rid)}
    assert run["metrics"]["quotes_verified"] == 7.0 and run["metrics"]["tokens_in"] >= 11000


def test_plan_answer_flows_into_p2_and_options_carry_swaps(p12, make_run, firestore_safe):
    rid = make_run()
    start_phase(p12, "u1", rid, "p1")
    qs = [{**q, "resolution": "compare_all"} for q in _run(p12, rid)["open_questions"]]
    resume_from_gate(p12, "u1", rid, "plan", {"open_questions": qs})
    run = _run(p12, rid)
    assert (run["status"], run["gate"]) == ("at_gate", "option")
    assert [o["id"] for o in run["options"]] == ["2N", "DR", "BLOCK"]
    assert all(o["swaps"][0]["to"] == "TX-3150" for o in run["options"])
    assert _out(p12, rid, "p2.annotate_options")["recommended"] == "BLOCK"  # compare_all: cheapest qualifying
    recheck = _out(p12, rid, "p2.power_recheck")["recheck"]
    assert recheck["2N"]["fail"] == 0 and recheck["2N"]["ikss_ka_after"] == 65.4
    ledger = [e["title"] for e in _events(p12, rid) if e["kind"] == "ledger"]
    assert "2N: TX-2500 replaced by TX-3150 (R15)" in ledger
    assert p12.engine.calls.count("power_recheck") == 3
    firestore_safe(p12.store)


def test_auto_mode_resolves_by_main_body_and_reaches_review(p12, make_run):
    rid = make_run(autonomy="auto")
    start_phase(p12, "u1", rid, "p1")
    run = _run(p12, rid)
    assert (run["status"], run["gate"]) == ("at_gate", "review")
    assert run["open_questions"][0]["resolution"] == "2N"
    ledger = [e["title"] for e in _events(p12, rid) if e["kind"] == "ledger"]
    assert "Q-redundancy resolved to 2N: the main body governs over the appendix." in ledger
    assert _out(p12, rid, "p2.annotate_options")["recommended"] == "2N"


class FlakyAnnotate(FakeEngine):
    """Fails twice: once inside the agent's tool call and once in the step's direct fallback call."""

    def __init__(self) -> None:
        super().__init__()
        self.failures_left = 2

    def annotate_options(self, scn, options, erp):
        if self.failures_left:
            self.failures_left -= 1
            raise RuntimeError("ERP timeout")
        return super().annotate_options(scn, options, erp)


def test_resume_mid_p2_reruns_only_unfinished_steps(p12, make_run):
    p12.engine = FlakyAnnotate()
    rid = make_run()
    start_phase(p12, "u1", rid, "p1")
    resume_from_gate(p12, "u1", rid, "plan")
    assert _run(p12, rid)["status"] == "failed"
    assert resume_run(p12, "u1", rid) is True
    assert _run(p12, rid)["gate"] == "option"
    assert p12.engine.calls.count("place_racks") == 1 and p12.engine.calls.count("power_options") == 1


def test_narration_with_free_numbers_is_replaced_by_the_template(p12, make_run):
    p12.runner.replies["layout:p2.place_racks"] = {"tool_calls": [{"name": "place_racks", "args": {}}],
                                                   "text": "Placed 48 racks in 6 rows."}
    rid = make_run()
    start_phase(p12, "u1", rid, "p1")
    resume_from_gate(p12, "u1", rid, "plan")
    msgs = [e["title"] for e in _events(p12, rid) if e["kind"] == "message" and e["agent"] == "layout"]
    assert msgs == ["Layout completed rack placement."]
