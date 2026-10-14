import importlib.util
import json
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(os.environ.get("KIRCHHOFF_LIVE") != "1", reason="set KIRCHHOFF_LIVE=1"),
              pytest.mark.skipif(importlib.util.find_spec("kirchhoff.engine") is None
                                 or importlib.util.find_spec("kirchhoff.engine.api") is None,
                                 reason="WS1 engine not landed")]
REPO = Path(__file__).resolve().parents[4]


def test_live_full_run_on_hall_b(tmp_path):
    import kirchhoff.engine.api as engine
    from kirchhoff.agents.adk_runner import AdkRunner
    from kirchhoff.agents.ports import load_erp_seed
    from kirchhoff.api.app import create_app
    from kirchhoff.runs.fakes import FakeEnterprise, build_fake_deps
    from kirchhoff.runs.revisions import run_revisions
    from kirchhoff.store.memory import MemoryStore

    scen = REPO / "scenarios"
    deps = build_fake_deps(MemoryStore(), scen, seed_dir=tmp_path, spawn=lambda fn: fn(), heartbeat_s=3600.0,
                           engine=engine, runner=AdkRunner(),
                           enterprise=FakeEnterprise(load_erp_seed(scen / "hall_a" / "erp_seed.yaml")))
    client, auth = TestClient(create_app(deps=deps, verify_token=lambda t: "u1")), {"Authorization": "Bearer t"}
    t0 = time.monotonic()
    rid = client.post("/api/runs", json={"project_id": "hall-b", "autonomy": "auto"}, headers=auth).json()["run_id"]
    run = deps.store.get_doc(f"workspaces/u1/runs/{rid}")
    assert (run["status"], run["gate"], run["selected_option"]) == ("at_gate", "review", "2N"), run
    revs = run_revisions(deps.store, "u1", rid)
    first = {f["id"] for f in deps.store.list_docs(f"workspaces/u1/revisions/{revs[0]['id']}/findings")
             if f["status"] == "fail"}
    assert first == {"R05:FA-01", "R11:H-Z2"}  # spec §9.6 golden first pass
    assert revs[-1]["check_summary"]["fail"] == 0 and len(revs) <= 3
    assert client.post(f"/api/runs/{rid}/gates/review", json={"decision": "approved"}, headers=auth).status_code == 202
    run = deps.store.get_doc(f"workspaces/u1/runs/{rid}")
    assert run["status"] == "done" and run["metrics"]["p4_blocked"] == 0.0
    print(json.dumps({"elapsed_s": round(time.monotonic() - t0, 1), **{k: run["metrics"].get(k) for k in
                      ("time_to_clean_s", "tokens_in", "tokens_out", "quotes_verified", "quotes_total")}}))
