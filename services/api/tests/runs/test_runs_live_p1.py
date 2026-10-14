import json
import os
import time
from pathlib import Path

import pytest

from kirchhoff.contracts import DesignBrief
from kirchhoff.runs.fakes import build_fake_deps
from kirchhoff.runs.leases import run_path
from kirchhoff.runs.orchestrator import start_phase
from kirchhoff.runs.outputs import load_outputs
from kirchhoff.runs.phase1 import S_INTAKE, run_p1
from kirchhoff.store.memory import MemoryStore

# Ruling P2-R14: the end-to-end P1 budget matches INTAKE.timeout_s (240 s, ruling P2-R11).
P1_BUDGET_S = 240.0


def _start_p1(deps, rid: str) -> float:
    deps.store.set_doc(run_path("u1", rid), {"id": rid, "project_id": "hall-b", "status": "running",
                                              "autonomy": "ask", "phase": "p1", "started_at": time.time()})
    t0 = time.monotonic()
    start_phase(deps, "u1", rid, "p1")
    return time.monotonic() - t0


def _diagnostics(deps, rid: str, elapsed: float) -> tuple[dict, DesignBrief | None]:
    """Everything a live P1 run should report, gathered without asserting anything, so it can be
    printed before the asserts. "backstop_fired" is the deterministic topology backstop's "assumed"
    ledger entry in the intake step (ruling P2-R13): False means the model reported the conflict itself."""
    run = deps.store.get_doc(run_path("u1", rid)) or {}
    out = load_outputs(deps.store, deps.blobs, run_path("u1", rid), S_INTAKE)
    brief = DesignBrief.model_validate(out["brief"]) if out else None
    events = deps.store.list_docs(f"{run_path('u1', rid)}/events")
    reqs = brief.requirements if brief else []
    return {"elapsed_s": round(elapsed, 1), "status": run.get("status"), "gate": run.get("gate"),
            "quotes_verified": sum(r.verified for r in reqs), "quotes_total": len(reqs),
            "intake_recall": brief.intake_score.get("recall") if brief else None,
            "backstop_fired": any(e["kind"] == "ledger" and e["step"] == S_INTAKE
                                  and e["payload"]["entry"]["kind"] == "assumed" for e in events)}, brief


@pytest.mark.live
@pytest.mark.skipif(os.environ.get("KIRCHHOFF_LIVE") != "1", reason="set KIRCHHOFF_LIVE=1")
def test_live_p1_on_vertex(scen_dir, tmp_path):
    from kirchhoff.agents.adk_runner import AdkRunner
    from kirchhoff.agents.runner import RecordingRunner

    runner = AdkRunner()
    if os.environ.get("KIRCHHOFF_RECORD_DIR"):
        runner = RecordingRunner(runner, Path(os.environ["KIRCHHOFF_RECORD_DIR"]))
    deps = build_fake_deps(MemoryStore(), scen_dir, seed_dir=tmp_path, spawn=lambda fn: fn(), heartbeat_s=3600.0,
                           runner=runner, phases={"p1": run_p1})
    elapsed = _start_p1(deps, "live-p1")
    diag, brief = _diagnostics(deps, "live-p1", elapsed)
    print(json.dumps(diag))  # before any assert, so a failing run still reports its numbers
    assert (diag["status"], diag["gate"]) == ("at_gate", "plan"), diag
    assert brief is not None
    verified = [r for r in brief.requirements if r.verified]
    assert len(verified) >= 12 and len(verified) >= 0.8 * len(brief.requirements)
    q = next(q for q in brief.open_questions if {c.clause for c in q.citations} == {"§4.2", "App. B"})
    assert q.default_resolution == "2N"
    assert brief.drawing_check["agrees"] is True, brief.drawing_check
    assert brief.intake_score["recall"] >= 0.6
    assert elapsed < P1_BUDGET_S, diag


_APP_B_REQ = {"key": "redundancy_alt", "clause": "App. B", "page": 7, "value": "BLOCK", "unit": None,
              "verbatim_quote": "Block or distributed redundancy acceptable, subject to the loading limits of §4.3."}


@pytest.mark.parametrize("model_reports_it", [True, False], ids=["model-reported", "backstop-derived"])
def test_backstop_diagnostic_offline(scen_dir, tmp_path, model_reports_it):
    # Offline proof that the live diagnostic tells "the model reported §4.2/App. B" apart from "the
    # deterministic backstop derived it" (ruling P2-R14), via the backstop's "assumed" ledger entry.
    from kirchhoff.runs.fakes import FAKE_REPLIES, CheckedStore

    ext = FAKE_REPLIES["intake:p1.extract"]["text"]
    replies = {} if model_reports_it else {"intake:p1.extract": {
        "text": {"requirements": [*ext["requirements"], _APP_B_REQ], "contradictions": []}}}
    deps = build_fake_deps(CheckedStore(), scen_dir, seed_dir=tmp_path, spawn=lambda fn: fn(), heartbeat_s=3600.0,
                           replies=replies, phases={"p1": run_p1})
    diag, brief = _diagnostics(deps, "offline-p1", _start_p1(deps, "offline-p1"))
    assert diag["backstop_fired"] is not model_reports_it, diag
    assert (diag["status"], diag["gate"]) == ("at_gate", "plan") and brief is not None
    assert diag["quotes_total"] == len(brief.requirements) and 0 < diag["quotes_verified"] <= diag["quotes_total"]
    assert diag["intake_recall"] == brief.intake_score["recall"]
    (q,) = [q for q in brief.open_questions if {c.clause for c in q.citations} == {"§4.2", "App. B"}]
    assert q.default_resolution == "2N"
