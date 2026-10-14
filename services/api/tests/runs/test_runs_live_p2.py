"""P2-R11 (fix round 1): the one live P2 tool-calling smoke. Runs P2 against the real
kirchhoff.engine.api facade AND the real AdkRunner (set by KIRCHHOFF_ADK_MODE, default "agent"
per this ruling) so Layout, Power, Cooling and Procurement each actually call a real tool through
a real Vertex AI round trip. No replay, no fakes for the runner. Starts directly at p2 (skips the
live P1 intake/orchestrator round trip, which test_runs_live_p1.py already covers) with the
redundancy question already resolved, to keep this to the one measurement the ruling asks for."""
import json
import os
import time
from pathlib import Path

import pytest

from kirchhoff.agents.ports import load_erp_seed
from kirchhoff.contracts import OpenQuestion, RunRecord
from kirchhoff.engine import api as real_engine
from kirchhoff.runs.blobs import MemoryBlobStore
from kirchhoff.runs.deps import Deps
from kirchhoff.runs.fakes import FakeEnterprise
from kirchhoff.runs.leases import run_path
from kirchhoff.runs.orchestrator import start_phase
from kirchhoff.runs.outputs import load_outputs
from kirchhoff.runs.phase2 import run_p2
from kirchhoff.store.memory import MemoryStore

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(os.environ.get("KIRCHHOFF_LIVE") != "1", reason="set KIRCHHOFF_LIVE=1")]

REPO_ROOT = Path(__file__).resolve().parents[4]
SCENARIOS_DIR = REPO_ROOT / "scenarios"


def test_live_p2_tool_calling_on_vertex():
    from kirchhoff.agents.adk_runner import AdkRunner

    if not (SCENARIOS_DIR / "hall_a" / "tender.yaml").exists():
        pytest.skip("real scenarios/hall_a fixtures not found")
    materials = load_erp_seed(SCENARIOS_DIR / "hall_a" / "erp_seed.yaml")
    deps = Deps(store=MemoryStore(), engine=real_engine, runner=AdkRunner(), enterprise=FakeEnterprise(materials=materials),
               blobs=MemoryBlobStore(), scenarios_dir=SCENARIOS_DIR, seed_dir=SCENARIOS_DIR,
               spawn=lambda fn: fn(), heartbeat_s=3600.0, phases={"p2": run_p2})
    uid, rid = "u1", "live-p2"
    q = OpenQuestion(id="Q-redundancy", text="The main body requires 2N; Appendix B allows block or distributed.",
                     options=["2N", "compare_all"], citations=[], default_resolution="2N", resolution=None)
    rec = RunRecord(id=rid, project_id="hall-b", status="running", autonomy="ask", phase="p2",
                    open_questions=[q], started_at=time.time())
    deps.store.set_doc(run_path(uid, rid), rec.model_dump(mode="json"))

    t0 = time.monotonic()
    start_phase(deps, uid, rid, "p2")
    elapsed = time.monotonic() - t0

    rp = run_path(uid, rid)
    run = deps.store.get_doc(rp)
    assert (run["status"], run["gate"]) == ("at_gate", "option"), run

    events = deps.store.list_docs(f"{rp}/events")
    tool_calls = {e["payload"]["tool"] for e in events if e["kind"] == "tool_call" and "tool" in e.get("payload", {})}
    # Layout, Power, Cooling and Procurement each really called their real engine tool through ADK.
    assert {"place_racks", "enumerate_topologies", "size_cdus", "annotate_options"} <= tool_calls

    ann = load_outputs(deps.store, deps.blobs, rp, "p2.annotate_options")
    options = {o["option"]["id"]: o["option"] for o in ann["options"]}
    assert ann["recommended"] == "2N"
    assert options["2N"]["swaps"] and options["2N"]["swaps"][0]["to"] == "TX-3150"

    tokens = dict(run.get("metrics") or {})
    print(json.dumps({"elapsed_s": round(elapsed, 1), "tokens_in": tokens.get("tokens_in"),
                      "tokens_out": tokens.get("tokens_out"), "tool_calls": sorted(tool_calls)}))
