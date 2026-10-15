"""P2 final fix wave, Important 1: an unfilled {value}/{limit}, a quantity in words or raw digits written by
an agent never reaches a surface the user sees or hears: lane narration, fix reasons, the Docs summary, the calc
report PDF and the plan-gate question text (the voice answer is covered in tests/api/test_api_voice.py)."""
import io

import pdfplumber
import pytest

from kirchhoff.agents.docs_export import BlobExporter
from kirchhoff.runs.leases import run_path
from kirchhoff.runs.orchestrator import resume_from_gate, start_phase
from kirchhoff.runs.outputs import load_outputs
from kirchhoff.runs.phase1 import run_p1
from kirchhoff.runs.phase2 import run_p2
from kirchhoff.runs.phase3 import run_p3
from kirchhoff.runs.revisions import run_revisions

LEAKS = {"placeholder": ("The drop is {value}, above the {limit} limit.", ["{value}", "{limit}"]),
         "number-words": ("The drop is two point one six percent.", ["two point one six percent"]),
         "digits": ("The drop is 7.77 percent.", ["7.77"])}
POWER_FIX = ("Power chose FA-01:cable-CBL-240-8P for R05:FA-01: largest voltage-drop margin per dollar, that is "
             "the limit minus the resulting drop, divided by the cost delta.")


@pytest.fixture
def p123(deps):
    deps.phases = {"p1": run_p1, "p2": run_p2, "p3": run_p3}
    return deps


def _leaky_replies(runner, leak: str) -> None:
    r = runner.replies
    r["orchestrator:p1.plan"] = {"text": {"summary": leak, "ask_human": ["Q-redundancy"]}}
    r["layout:p2.place_racks"] = {"tool_calls": [{"name": "place_racks", "args": {}}], "text": leak}
    r["power:p2.power_options"] = {"tool_calls": [{"name": "enumerate_topologies", "args": {}}],
                                   "text": {"offer": ["2N", "DR", "BLOCK"], "reason": leak}}
    r["procurement:p2.annotate_options"] = {"tool_calls": [{"name": "annotate_options", "args": {}}], "text": leak}
    r["layout:p3.route"] = {"tool_calls": [{"name": "route_busways", "args": {}}], "text": leak}
    r["power:p3.fix.1:R05:FA-01"] = {"text": {"candidate_id": "FA-01:cable-CBL-240-8P", "reason": leak}}
    r["docs:p3.docs"] = {"text": {"order": ["summary", "fixes"], "summary": leak}}


def _to_review(d, make_run) -> str:
    rid = make_run()
    start_phase(d, "u1", rid, "p1")
    resume_from_gate(d, "u1", rid, "plan")
    resume_from_gate(d, "u1", rid, "option", {"selected_option": "2N"})
    return rid


def _message(d, rid, step: str) -> str:
    (e,) = [e for e in d.store.list_docs(f"{run_path('u1', rid)}/events") if e["step"] == step
            and e["kind"] == "message" and e["agent"] in ("orchestrator", "layout", "power", "procurement", "docs")]
    return e["title"]


@pytest.mark.parametrize("name", list(LEAKS))
def test_no_leak_reaches_narration_fix_reasons_docs_summary_or_the_pdf(p123, make_run, name):
    leak, needles = LEAKS[name]
    _leaky_replies(p123.runner, leak)
    p123.exporter = BlobExporter(p123.blobs)
    rid = _to_review(p123, make_run)
    # P2 final fix wave (ruling P2-R19): the fallback is now the engine-record template for each step
    # (ruling R14 -- code-authored text built only from engine values, never the leaking LLM text), not
    # the flat generic "{Agent} completed {step}." -- but the leak itself must still never surface.
    assert _message(p123, rid, "p1.plan") == ("Orchestrator built a 13-step plan from 7 verified "
                                              "requirement(s), with 1 question(s) for you to decide.")
    assert _message(p123, rid, "p2.place_racks") == ("Layout placed 2 rack(s) in 2 row(s) with the engine's "
                                                      "default pitch.")
    assert _message(p123, rid, "p2.power_options") == ("Power compared 3 topology option(s) (2N, BLOCK, DR) "
                                                        "and offered 3 to the engineer.")
    assert _message(p123, rid, "p2.annotate_options") == ("Procurement checked lead times for 15 catalogue "
                                                           "item(s) across 3 option(s).")
    assert _message(p123, rid, "p3.route") == ("Layout routed 2 connection(s), including 2 feeder busway(s), "
                                               "with the engine's default candidate routes.")
    r1, r2 = run_revisions(p123.store, "u1", rid)
    fix = p123.store.get_doc(f"workspaces/u1/revisions/{r1['id']}/findings/R05:FA-01")["fix"]
    assert fix["reason"] == POWER_FIX
    docs = load_outputs(p123.store, p123.blobs, run_path("u1", rid), "p3.docs")
    assert docs["summary"] == (f"Docs prepared the calc report and BOQ for {r2['id']}: 9 check(s), 0 failing, "
                               "2 fix(es) applied.")
    pdf = p123.blobs.get(f"workspaces/u1/{docs['files'][0]['path']}")
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        text = " ".join(" ".join((page.extract_text() or "").split()) for page in doc.pages)
    assert POWER_FIX.split(":")[0] in text and docs["summary"] in text
    for needle in [*needles, "{", "}"]:
        assert needle not in text
