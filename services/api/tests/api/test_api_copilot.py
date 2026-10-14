import time
from pathlib import Path

from kirchhoff.agents.copilot import load_seed_bundle
from kirchhoff.api import copilot_routes
from kirchhoff.contracts import ProjectBundle
from kirchhoff.runs.fakes import FakeEngine

REPO_ROOT = Path(__file__).resolve().parents[4]
BUILD_HALL_A_PATH = "apps/web/public/demo/projects/hall-a.json"


def _read_build_hall_a() -> str | None:
    """The WS4 seed bundle lives in the working tree only on the `build` branch (merged there by the
    controller); this worktree (ws2-agents) never checks it out. Read the real, engine-built bundle
    straight out of `build`'s git history without touching any working-tree file."""
    import subprocess

    # Prefer a working-tree copy if one is ever present (e.g. after a merge into this worktree).
    local = REPO_ROOT / BUILD_HALL_A_PATH
    if local.exists():
        return local.read_text(encoding="utf-8")
    try:
        out = subprocess.run(["git", "show", f"build:{BUILD_HALL_A_PATH}"], cwd=REPO_ROOT,
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 and out.stdout else None


def _post(client, auth, path, body):
    return client.post(path, json=body, headers=auth)


def test_what_if_on_a_seed_revision(client, seeded, auth):
    r = _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r2", "param": "rack_kw", "value": 200})
    assert r.status_code == 200
    body = r.json()
    assert body["revision_ref"] == "seed:hall-a@r2" and body["impact_chain"]
    assert {"R01", "R02", "R08"} <= {f["rule_id"] for f in body["findings"] if f["status"] == "fail"}


def test_what_if_on_a_workspace_revision(client, seeded, auth):
    model = load_seed_bundle(seeded.seed_dir, "hall-a").revisions[1].model
    seeded.store.set_doc("workspaces/u1/revisions/x-r2", {"id": "x-r2", "model": None,
                                                          "model_url": "revisions/x-r2/model.json"})
    seeded.blobs.put("workspaces/u1/revisions/x-r2/model.json", model.model_dump_json().encode(), "application/json")
    r = _post(client, auth, "/api/what-if", {"revision_ref": "ws:x-r2", "param": "rack_kw", "value": 150})
    assert r.status_code == 200 and r.json()["findings"] == []


def test_what_if_errors(client, seeded, auth):
    assert _post(client, auth, "/api/what-if", {"revision_ref": "foo", "param": "rack_kw", "value": 1}).json() == \
        {"detail": "bad_revision_ref"}
    assert _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r9", "param": "rack_kw",
                                                "value": 1}).status_code == 404
    assert _post(client, auth, "/api/what-if", {"revision_ref": "ws:nope", "param": "rack_kw",
                                                "value": 1}).status_code == 404
    assert _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r2", "param": "voltage",
                                                "value": 1}).status_code == 422


class SlowEngine(FakeEngine):
    def what_if(self, *args, **kwargs):
        time.sleep(0.3)
        return super().what_if(*args, **kwargs)


def test_what_if_times_out(client, seeded, auth, monkeypatch):
    seeded.engine = SlowEngine()
    monkeypatch.setattr(copilot_routes, "WHAT_IF_TIMEOUT_S", 0.05)
    r = _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r2", "param": "rack_kw", "value": 200})
    assert r.status_code == 504 and r.json() == {"detail": "timeout"}


def test_explain_fills_placeholders_from_the_engine_record(client, seeded, auth):
    r = _post(client, auth, "/api/explain", {"revision_ref": "seed:hall-a@r1", "finding_id": "R05:FA-01"})
    assert r.json() == {"text": "FA-01 has a voltage drop of 2.16%, above the 2% limit in §4.6. It is the longest "
                                "A-side feeder from A1."}


def test_explain_with_free_numbers_uses_the_rule_template(client, seeded, auth):
    seeded.runner.replies["copilot:explain:R05:FA-01"] = {"text": "The drop is 2.16% because it is 82 m long."}
    r = _post(client, auth, "/api/explain", {"revision_ref": "seed:hall-a@r1", "finding_id": "R05:FA-01"})
    assert r.json() == {"text": "Voltage drop: 2.16% against a limit of 2%."}


def test_explain_survives_a_model_failure(client, seeded, auth):
    seeded.runner.replies["copilot:explain:R05:FA-01"] = {"raise": "vertex down"}
    r = _post(client, auth, "/api/explain", {"revision_ref": "seed:hall-a@r1", "finding_id": "R05:FA-01"})
    assert r.json() == {"text": "Voltage drop: 2.16% against a limit of 2%."}


def test_explain_unknown_finding(client, seeded, auth):
    r = _post(client, auth, "/api/explain", {"revision_ref": "seed:hall-a@r1", "finding_id": "R99:X"})
    assert r.status_code == 404 and r.json() == {"detail": "finding_not_found"}


def test_explain_with_raw_digits_never_leaks_them_into_the_response(client, seeded, auth):
    """Trust rule (spec §6.3): raw LLM digits must never reach the response, even disguised inside a
    sentence that also carries the correct-looking number."""
    seeded.runner.replies["copilot:explain:R05:FA-01"] = {"text": "Careful review shows the drop is 9.99% here."}
    r = _post(client, auth, "/api/explain", {"revision_ref": "seed:hall-a@r1", "finding_id": "R05:FA-01"})
    body = r.json()
    assert "9.99" not in body["text"]
    assert body == {"text": "Voltage drop: 2.16% against a limit of 2%."}


# --- Real-engine verification (controller's measured 200 kW what-if beat): loads the actual WS4 seed bundle
# built on `build` (apps/web/public/demo/projects/hall-a.json) and runs the real engine's what_if through the
# live API wiring, rather than the FakeEngine `seeded` fixture above.
def test_what_if_200kw_on_the_real_hall_a_seed_bundle_matches_the_controllers_measured_count(tmp_path, auth):
    import pytest

    raw = _read_build_hall_a()
    if raw is None:
        pytest.skip("WS4 seed bundle (apps/web/public/demo/projects/hall-a.json) not found in this worktree "
                    "or on the `build` ref")
    # Fail loudly, not silently, if the file we found is not the real inlined-model bundle (the brief's
    # blocker condition): a seed revision with a null `model` cannot run a real what-if at all.
    bundle = ProjectBundle.model_validate_json(raw)
    r2 = next(rev for rev in bundle.revisions if rev.id == "r2")
    assert r2.model is not None, "WS4 seed bundle revision r2 does not inline `model` (field path: revisions[].model)"

    from fastapi.testclient import TestClient
    from kirchhoff.api.app import create_app
    from kirchhoff.engine import api as real_engine
    from kirchhoff.engine.scenario import scenarios_root
    from kirchhoff.runs.fakes import CheckedStore, FakeEnterprise, build_fake_deps

    real_scenarios_dir = scenarios_root()  # auto-discovers <repo>/scenarios by walking up from engine/scenario.py
    assert (real_scenarios_dir / "hall_a" / "tender.yaml").exists()
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    seed_dir.joinpath("hall-a.json").write_text(raw, encoding="utf-8")
    # Use the real engine's own default catalogue (scenarios/hall_a/erp_seed.yaml), not the FakeEnterprise
    # catalogue build_fake_deps defaults to -- the 60/18 measured count is against the real engine's ERP.
    real_catalogue = real_engine.default_erp().all()
    deps = build_fake_deps(CheckedStore(), real_scenarios_dir, seed_dir=seed_dir, engine=real_engine,
                           enterprise=FakeEnterprise(real_catalogue), spawn=lambda fn: fn(), heartbeat_s=3600.0)
    client = TestClient(create_app(deps=deps, verify_token=lambda token: "u1"))
    r = _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r2", "param": "rack_kw", "value": 200})
    assert r.status_code == 200
    body = r.json()
    assert len(body["findings"]) == 60
    assert len(body["impact_chain"]) == 18
