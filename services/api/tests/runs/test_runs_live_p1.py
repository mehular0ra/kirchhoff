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
from kirchhoff.runs.phase1 import run_p1
from kirchhoff.store.memory import MemoryStore

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(os.environ.get("KIRCHHOFF_LIVE") != "1", reason="set KIRCHHOFF_LIVE=1")]


def test_live_p1_on_vertex(scen_dir, tmp_path):
    from kirchhoff.agents.adk_runner import AdkRunner
    from kirchhoff.agents.runner import RecordingRunner

    runner = AdkRunner()
    if os.environ.get("KIRCHHOFF_RECORD_DIR"):
        runner = RecordingRunner(runner, Path(os.environ["KIRCHHOFF_RECORD_DIR"]))
    deps = build_fake_deps(MemoryStore(), scen_dir, seed_dir=tmp_path, spawn=lambda fn: fn(), heartbeat_s=3600.0,
                           runner=runner, phases={"p1": run_p1})
    rid = "live-p1"
    deps.store.set_doc(run_path("u1", rid), {"id": rid, "project_id": "hall-b", "status": "running",
                                              "autonomy": "ask", "phase": "p1", "started_at": time.time()})
    t0 = time.monotonic()
    start_phase(deps, "u1", rid, "p1")
    elapsed = time.monotonic() - t0
    run = deps.store.get_doc(run_path("u1", rid))
    assert (run["status"], run["gate"]) == ("at_gate", "plan"), run
    brief = DesignBrief.model_validate(load_outputs(deps.store, deps.blobs, run_path("u1", rid), "p1.intake")["brief"])
    verified = [r for r in brief.requirements if r.verified]
    assert len(verified) >= 12 and len(verified) >= 0.8 * len(brief.requirements)
    q = next(q for q in brief.open_questions if {c.clause for c in q.citations} == {"§4.2", "App. B"})
    assert q.default_resolution == "2N"
    assert brief.drawing_check["agrees"] is True, brief.drawing_check
    assert brief.intake_score["recall"] >= 0.6
    assert elapsed < 120
    print(json.dumps({"elapsed_s": round(elapsed, 1), **brief.intake_score}))
