import time

from fastapi.testclient import TestClient

from kirchhoff.api import inbox_routes
from kirchhoff.api.app import create_app
from kirchhoff.runs.fakes import CheckedStore, build_fake_deps

SWAP = ("26-week limit; the 2.5 MVA unit TX-2500 is 98 weeks with none in stock; "
        "expect an in-stock swap to TX-3150 (3.15 MVA, 6 in stock).")


def test_inbox_needs_a_token(client, inbox_ready):
    assert client.get("/api/inbox").status_code == 401
    assert client.post("/api/inbox/em-hall-b/triage").status_code == 401
    assert client.post("/api/inbox/em-hall-b/pursue").status_code == 401


def test_inbox_without_a_seed_is_503(tmp_path):
    deps = build_fake_deps(CheckedStore(), tmp_path)
    r = TestClient(create_app(deps=deps, verify_token=lambda t: "u1")).get("/api/inbox", headers={"Authorization": "Bearer t"})
    assert r.status_code == 503 and r.json() == {"detail": "inbox_unavailable"}


def test_get_inbox_returns_the_seed_newest_first(client, inbox_ready, auth):
    body = client.get("/api/inbox", headers=auth).json()
    assert body["mailbox"] == "bids@meridian-power.example" and body["label"] == "sandbox (simulated)"
    assert [e["id"] for e in body["emails"]][:2] == ["em-hall-b", "em-tapti-brochure"]
    assert {e["status"] for e in body["emails"]} == {"new"} and all(e["pursue"] is None for e in body["emails"])


def test_triage_is_live_only_for_hall_b(client, inbox_ready, auth):
    r = client.post("/api/inbox/em-konkan-rfi/triage", headers=auth)
    assert r.status_code == 409 and r.json() == {"detail": "precomputed"}
    assert client.post("/api/inbox/em-nope/triage", headers=auth).status_code == 404


def test_live_triage_of_hall_b_is_stored_in_the_overlay(client, inbox_ready, auth, firestore_safe):
    r = client.post("/api/inbox/em-hall-b/triage", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "live" and body["fit"]["verdict"] == "pursue" and body["fit"]["supply"]["text"] == SWAP
    assert (body["quotes_verified"], body["quotes_total"]) == (7, 7)
    hall_b = next(e for e in client.get("/api/inbox", headers=auth).json()["emails"] if e["id"] == "em-hall-b")
    assert hall_b["status"] == "triaged" and hall_b["triage"] == body
    firestore_safe(inbox_ready.store)


def test_triage_failure_timeout_and_rate_limit(client, inbox_ready, auth, monkeypatch):
    key = "inbox:triage:em-hall-b"
    recorded, inbox_ready.runner.replies[key] = inbox_ready.runner.replies[key], {"raise": "vertex down"}
    r = client.post("/api/inbox/em-hall-b/triage", headers=auth)
    assert r.status_code == 502 and r.json() == {"detail": "triage_failed"}
    inbox_ready.runner.replies[key] = recorded

    def slow(*args):
        time.sleep(0.3)

    monkeypatch.setattr(inbox_routes, "SUPPLY_FN", slow)
    monkeypatch.setattr(inbox_routes, "TRIAGE_TIMEOUT_S", 0.05)
    r = client.post("/api/inbox/em-hall-b/triage", headers=auth)
    assert r.status_code == 504 and r.json() == {"detail": "timeout"}
    now = inbox_ready.clock()
    inbox_ready.store.set_doc("workspaces/u1", {"triage_starts": [now - 60] * 10})
    r = client.post("/api/inbox/em-hall-b/triage", headers=auth)
    assert r.status_code == 429 and r.json() == {"detail": "triage_rate_limit"}


def test_pursue_hall_b_sets_qualifying_and_opens_its_intake(client, inbox_ready, auth):
    r = client.post("/api/inbox/em-hall-b/pursue", headers=auth)
    assert r.status_code == 409 and r.json() == {"detail": "not_triaged"}  # no capture in the seed, no live triage
    client.post("/api/inbox/em-hall-b/triage", headers=auth)
    r = client.post("/api/inbox/em-hall-b/pursue", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json() == {"email_id": "em-hall-b", "project_id": "hall-b", "project_name": None,
                        "project_created": False, "opportunity_id": "opp-hall-b",
                        "opportunity_name": "Hall B design-build", "stage": "Qualification",
                        "previous_stage": "Design in progress", "opportunity_created": False,
                        "open": "/app/p/hall-b"}
    assert inbox_ready.enterprise.stages[("u1", "opp-hall-b")].stage == "Qualification"
    assert client.post("/api/inbox/em-hall-b/pursue", headers=auth).json() == r.json()  # idempotent
    hall_b = next(e for e in client.get("/api/inbox", headers=auth).json()["emails"] if e["id"] == "em-hall-b")
    assert hall_b["status"] == "pursued" and hall_b["pursue"]["stage"] == "Qualification"


def test_pursue_never_reopens_a_signed_deal(client, inbox_ready, auth):
    inbox_ready.enterprise.set_opportunity_stage("u1", "opp-hall-b", "Design approved")
    client.post("/api/inbox/em-hall-b/triage", headers=auth)
    body = client.post("/api/inbox/em-hall-b/pursue", headers=auth).json()
    assert (body["stage"], body["previous_stage"]) == ("Design approved", "Design approved")


def test_pursue_creates_the_project_and_the_opportunity(client, inbox_precomputed, auth, firestore_safe):
    deps = inbox_precomputed
    r = client.post("/api/inbox/em-suryodaya-solar/pursue", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["project_id"], body["project_created"], body["open"]) == ("bid-suryodaya-solar", True, None)
    assert body["project_name"] == "Suryodaya Renewables · Enquiry: solar EPC near Anantapur"
    assert (body["opportunity_id"], body["opportunity_created"], body["stage"], body["previous_stage"]) == \
        ("opp-em-suryodaya-solar", True, "Qualification", None)
    project = deps.store.get_doc("workspaces/u1/projects/bid-suryodaya-solar")
    assert (project["asset_pack"], project["state"], project["client"]) == ("solar", "draft", "Suryodaya Renewables")
    assert "opp-em-suryodaya-solar" in {o.id for o in deps.enterprise.list_opportunities("u1")}
    vindhya = client.post("/api/inbox/em-vindhya-boq/pursue", headers=auth).json()
    assert (vindhya["opportunity_id"], vindhya["previous_stage"], vindhya["project_id"]) == \
        ("opp-vindhya-cpp", "Qualification", "bid-vindhya-boq")
    for email_id in ("em-narmada-400kv", "em-tapti-brochure"):  # decline, not a bid
        r = client.post(f"/api/inbox/{email_id}/pursue", headers=auth)
        assert r.status_code == 409 and r.json() == {"detail": "cannot_pursue"}
    firestore_safe(deps.store)


def test_pursue_reports_an_unavailable_crm(client, inbox_precomputed, auth, monkeypatch):
    def down(uid):
        raise RuntimeError("sandbox down")

    monkeypatch.setattr(inbox_precomputed.enterprise, "list_opportunities", down)
    r = client.post("/api/inbox/em-suryodaya-solar/pursue", headers=auth)
    assert r.status_code == 502 and r.json() == {"detail": "enterprise_unavailable"}


def test_reset_clears_the_inbox_overlay(client, inbox_ready, auth):
    client.post("/api/inbox/em-hall-b/triage", headers=auth)
    client.post("/api/inbox/em-hall-b/pursue", headers=auth)
    assert client.post("/api/workspace/reset", headers=auth).json() == {"ok": True}
    assert inbox_ready.store.list_docs("workspaces/u1/inbox") == []
    assert ("u1", "opp-hall-b") not in inbox_ready.enterprise.stages


def test_each_visitor_sees_only_their_own_overlay(client, inbox_ready, auth):
    """u1 triages and pursues; a different visitor on the same deployment still sees every email as new."""
    client.post("/api/inbox/em-hall-b/triage", headers=auth)
    client.post("/api/inbox/em-hall-b/pursue", headers=auth)
    other = TestClient(create_app(deps=inbox_ready, verify_token=lambda token: "u2"))
    body = other.get("/api/inbox", headers=auth).json()
    assert {e["status"] for e in body["emails"]} == {"new"} and all(e["triage"] is None for e in body["emails"])
    assert other.post("/api/inbox/em-hall-b/pursue", headers=auth).json() == {"detail": "not_triaged"}
