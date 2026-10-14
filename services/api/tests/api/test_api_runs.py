import pytest
from fastapi.testclient import TestClient

from kirchhoff.api.app import create_app
from kirchhoff.runs.leases import LIVE_RUNS_DOC, run_path
from kirchhoff.runs.phase1 import run_p1
from kirchhoff.runs.phase2 import run_p2
from kirchhoff.runs.steps import PhaseOutcome

NEW_RUN = {"project_id": "hall-b", "autonomy": "ask"}


def review_stub(ctx):
    return PhaseOutcome(gate="review")


@pytest.fixture
def staged(deps):
    deps.phases = {"p1": run_p1, "p2": run_p2, "p3": review_stub}
    return deps


def _run(d, rid):
    return d.store.get_doc(run_path("u1", rid))


def _start(client, auth) -> str:
    r = client.post("/api/runs", json=NEW_RUN, headers=auth)
    assert r.status_code == 202, r.text
    return r.json()["run_id"]


def test_runs_require_a_token(client):
    assert client.post("/api/runs", json=NEW_RUN).status_code == 401


def test_create_run_starts_p1_and_parks_at_the_plan_gate(client, staged, auth):
    rid = _start(client, auth)
    run = _run(staged, rid)
    assert (run["status"], run["gate"], run["project_id"]) == ("at_gate", "plan", "hall-b")
    assert len(staged.store.get_doc("workspaces/u1")["run_starts"]) == 1


def test_only_hall_b_runs_live(client, auth):
    assert client.post("/api/runs", json={"project_id": "hall-a"}, headers=auth).status_code == 422


def test_visitor_rate_limit(client, staged, auth):
    now = staged.clock()
    staged.store.set_doc("workspaces/u1", {"created_at": now, "run_starts": [now - 60] * 5})
    r = client.post("/api/runs", json=NEW_RUN, headers=auth)
    assert r.status_code == 429 and r.json() == {"detail": "visitor_rate_limit"}


def test_global_cap_offers_replay_and_leaves_no_run(client, staged, auth):
    now = staged.clock()
    staged.store.set_doc(LIVE_RUNS_DOC, {"runs": {"a__1": now, "b__2": now, "c__3": now}})
    r = client.post("/api/runs", json=NEW_RUN, headers=auth)
    assert r.status_code == 429 and r.json() == {"detail": "global_cap", "offer": "replay"}
    assert staged.store.list_docs("workspaces/u1/runs") == []


def test_plan_gate_validates_then_starts_p2(client, staged, auth):
    rid = _start(client, auth)
    wrong = client.post(f"/api/runs/{rid}/gates/option", json={"option_id": "2N"}, headers=auth)
    assert wrong.status_code == 409 and wrong.json() == {"detail": "wrong_state"}
    bad = client.post(f"/api/runs/{rid}/gates/plan", json={"answers": {"Q-redundancy": "3N"}}, headers=auth)
    assert bad.status_code == 422 and bad.json()["detail"] == "invalid_answer"
    ok = client.post(f"/api/runs/{rid}/gates/plan", headers=auth,
                     json={"answers": {"Q-redundancy": "compare_all"},
                           "plan_notes": {"p2.place_racks": "Keep R1 close to room A"}})
    assert ok.status_code == 202
    run = _run(staged, rid)
    assert run["gate"] == "option" and run["open_questions"][0]["resolution"] == "compare_all"
    assert next(p for p in run["plan"] if p["id"] == "p2.place_racks")["note"] == "Keep R1 close to room A"


def test_option_gate_selects_and_starts_p3(client, staged, auth):
    rid = _start(client, auth)
    client.post(f"/api/runs/{rid}/gates/plan", json={}, headers=auth)
    assert client.post(f"/api/runs/{rid}/gates/option", json={"option_id": "XX"}, headers=auth).status_code == 422
    assert client.post(f"/api/runs/{rid}/gates/option", json={"option_id": "2N"}, headers=auth).status_code == 202
    run = _run(staged, rid)
    assert (run["gate"], run["selected_option"]) == ("review", "2N")


def test_resume_and_ownership(client, staged, auth):
    rid = _start(client, auth)
    assert client.post(f"/api/runs/{rid}/resume", headers=auth).json() == {"resumed": False}
    other = TestClient(create_app(deps=staged, verify_token=lambda token: "u2"))
    assert other.post(f"/api/runs/{rid}/resume", headers=auth).status_code == 404
    assert other.post(f"/api/runs/{rid}/gates/plan", json={}, headers=auth).status_code == 404
    r = other.post(f"/api/runs/{rid}/gates/review", json={"decision": "approved"}, headers=auth)
    assert r.status_code == 404
    assert staged.store.list_docs("workspaces/u1/approvals") == []
    assert staged.store.list_docs("workspaces/u2/approvals") == []


def test_gate_expiry(client, staged, auth):
    rid = _start(client, auth)
    run = _run(staged, rid)
    staged.store.set_doc(run_path("u1", rid), {**run, "metrics": {**run["metrics"],
                                                                 "gate_entered_at": staged.clock() - 90_000}})
    r = client.post(f"/api/runs/{rid}/gates/plan", json={}, headers=auth)
    assert r.status_code == 409 and r.json() == {"detail": "gate_expired"}
    assert _run(staged, rid)["status"] == "expired"
