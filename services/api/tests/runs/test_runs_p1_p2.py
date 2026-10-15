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


def test_narration_with_free_numbers_is_replaced_by_the_engine_record_template(p12, make_run):
    """P2 final fix wave (ruling P2-R19): a digit/number-word slip still falls back, but the fallback
    template is now built from the engine's OWN place_racks output (2 racks, rows R1/R3 in the fake), not
    the flat generic '{Agent} completed {step}.' -- this is code-authored text (ruling R14), so it may
    carry those engine-derived digits even though sanitize() runs with placeholders=False."""
    p12.runner.replies["layout:p2.place_racks"] = {"tool_calls": [{"name": "place_racks", "args": {}}],
                                                   "text": "Placed 48 racks in 6 rows."}
    rid = make_run()
    start_phase(p12, "u1", rid, "p1")
    resume_from_gate(p12, "u1", rid, "plan")
    msgs = [e["title"] for e in _events(p12, rid) if e["kind"] == "message" and e["agent"] == "layout"]
    assert msgs == ["Layout placed 2 racks in 2 rows with the engine's default pitch."]


def test_clean_layout_narration_passes_through_unchanged(p12, make_run):
    """A clean LLM reply (no digits, no number words, no braces) is left untouched -- the fallback
    template only fires when sanitize() actually rejects the text."""
    rid = make_run()
    start_phase(p12, "u1", rid, "p1")
    resume_from_gate(p12, "u1", rid, "plan")
    msgs = [e["title"] for e in _events(p12, rid) if e["kind"] == "message" and e["agent"] == "layout"]
    assert msgs == ["Layout placed the racks in rows R1 and R3 with the engine default."]


def test_power_topology_narration_falls_back_to_the_engine_record_template(p12, make_run):
    """Power's own narration (p2.power_options) slips a word-number ("all three topologies"); the
    fallback must name the engine's own option ids and counts, not the generic template."""
    p12.runner.replies["power:p2.power_options"] = {
        "tool_calls": [{"name": "enumerate_topologies", "args": {}}],
        "text": {"offer": ["2N", "DR", "BLOCK"], "reason": "All three topologies pass R01 at minimum rating."}}
    rid = make_run()
    start_phase(p12, "u1", rid, "p1")
    resume_from_gate(p12, "u1", rid, "plan")
    msgs = [e["title"] for e in _events(p12, rid) if e["kind"] == "message" and e["agent"] == "power"
            and e["step"] == "p2.power_options"]
    assert msgs == ["Power compared 3 topology options (2N, BLOCK, DR) and offered 3 to the engineer."]


def test_cooling_narration_falls_back_to_the_engine_record_template(p12, make_run):
    """Cooling's own narration slips "zero single points of failure" (a number word); the fallback must
    be built from the engine's size_cooling output (6 CDUs, zones Z1/Z2 in the fake), not the generic
    template."""
    p12.runner.replies["cooling:p2.cooling_sizing"] = {
        "tool_calls": [{"name": "size_cdus", "args": {}}, {"name": "hydraulic_zones", "args": {}}],
        "text": "Cooling sized the CDUs with zero single points of failure across both zones."}
    rid = make_run()
    start_phase(p12, "u1", rid, "p1")
    resume_from_gate(p12, "u1", rid, "plan")
    msgs = [e["title"] for e in _events(p12, rid) if e["kind"] == "message" and e["agent"] == "cooling"]
    assert msgs == ["Cooling sized 6 CDUs across 2 zones, N+1 per zone."]


def test_procurement_narration_falls_back_to_the_engine_record_template(p12, make_run):
    """Procurement's own narration slips a number word ("all three options"); the fallback must come from
    the engine's annotate_options output (5 equipment lines per the fake model, 3 options)."""
    p12.runner.replies["procurement:p2.annotate_options"] = {
        "tool_calls": [{"name": "annotate_options", "args": {}}],
        "text": "All three options now ship within the tender's lead-time limit."}
    rid = make_run()
    start_phase(p12, "u1", rid, "p1")
    resume_from_gate(p12, "u1", rid, "plan")
    msgs = [e["title"] for e in _events(p12, rid) if e["kind"] == "message" and e["agent"] == "procurement"]
    assert msgs == ["Procurement checked lead times for 15 catalogue items across 3 options."]


def test_power_recheck_narration_falls_back_to_the_engine_record_template(p12, make_run):
    """Power's fault-level re-check narration slips a number word; the fallback names the swapped option
    ids the engine itself produced (all three options carry the TX-2500 -> TX-3150 swap in the fake)."""
    p12.runner.replies["power:p2.power_recheck"] = {
        "tool_calls": [{"name": "recheck_swapped_options", "args": {}}],
        "text": "All three swapped options still pass R01, R04 and R04b."}
    rid = make_run()
    start_phase(p12, "u1", rid, "p1")
    qs = [{**q, "resolution": "compare_all"} for q in _run(p12, rid)["open_questions"]]
    resume_from_gate(p12, "u1", rid, "plan", {"open_questions": qs})
    msgs = [e["title"] for e in _events(p12, rid) if e["kind"] == "message" and e["agent"] == "power"
            and e["step"] == "p2.power_recheck"]
    assert msgs == ["Power re-checked 3 swapped options (2N, BLOCK, DR) after the R15 swap."]


def test_orchestrator_plan_narration_falls_back_to_the_engine_record_template(p12, make_run):
    """Orchestrator's planning narration slips a number word; the fallback is built only from the brief's
    own verified-requirement count and the plan length -- both engine/code-derived, never the LLM's."""
    p12.runner.replies["orchestrator:p1.plan"] = {
        "text": {"summary": "All seven verified requirements are covered by the plan.",
                 "ask_human": ["Q-redundancy"]}}
    rid = make_run()
    start_phase(p12, "u1", rid, "p1")
    msgs = [e["title"] for e in _events(p12, rid) if e["kind"] == "message" and e["agent"] == "orchestrator"]
    assert msgs == ["Orchestrator built a 13-step plan from 7 verified requirements, with "
                    "1 question for you to decide."]
