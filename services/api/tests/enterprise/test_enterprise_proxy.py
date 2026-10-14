import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kirchhoff.api.auth import make_current_uid
from kirchhoff.api.enterprise_proxy import make_router
from kirchhoff.contracts import PRLine
from kirchhoff.enterprise import client as client_mod
from kirchhoff.enterprise.client import LocalEnterpriseClient
from kirchhoff.store.memory import MemoryStore

TOKENS = {"tok-u1": "u1", "tok-u2": "u2"}
H1 = {"Authorization": "Bearer tok-u1"}
H2 = {"Authorization": "Bearer tok-u2"}
PATHS = ("/api/enterprise/erp/materials", "/api/enterprise/erp/prs", "/api/enterprise/crm/opportunities")
LINES = [PRLine(material_id="TX-3150", description="TX-3150 item", qty=6, unit_price=100.0, lead_time_weeks=12)]


def _client(enterprise) -> TestClient:
    app = FastAPI()
    app.include_router(make_router(MemoryStore(), make_current_uid(lambda t: TOKENS[t]), client=enterprise))
    return TestClient(app)


@pytest.fixture(autouse=True)
def _no_appcheck(monkeypatch):
    monkeypatch.delenv("KIRCHHOFF_REQUIRE_APPCHECK", raising=False)


def test_every_route_requires_a_token(sandbox):
    client = _client(LocalEnterpriseClient(sandbox))
    assert [client.get(p).status_code for p in PATHS] == [401, 401, 401]


def test_materials(sandbox):
    body = _client(LocalEnterpriseClient(sandbox)).get(PATHS[0], headers=H1).json()
    assert [m["id"] for m in body] == ["BW-1600", "TX-2500", "TX-3150"]


def test_prs_show_the_seed_plus_only_the_callers_own(sandbox):
    client = _client(LocalEnterpriseClient(sandbox))
    mine = sandbox.create_pr("u1", "hall-b", "x-r2", LINES, idempotency_key="k")
    assert [p["id"] for p in client.get(PATHS[1], headers=H1).json()] == [mine.id, "PR-2026-0142"]
    assert [p["id"] for p in client.get(PATHS[1], headers=H2).json()] == ["PR-2026-0142"]


def test_opportunities_apply_only_the_callers_overlay(sandbox):
    client = _client(LocalEnterpriseClient(sandbox))
    sandbox.set_opportunity_stage("u1", "opp-hall-b", "Design approved")

    def stage(headers):
        return {o["id"]: o["stage"] for o in client.get(PATHS[2], headers=headers).json()}["opp-hall-b"]

    assert stage(H1) == "Design approved" and stage(H2) == "Design in progress"


def test_sandbox_failure_is_a_502():
    class Down:
        def list_materials(self):
            raise RuntimeError("down")

        def list_prs(self, uid):
            raise RuntimeError("down")

        def list_opportunities(self, uid):
            raise RuntimeError("down")

    client = _client(Down())
    for path in PATHS:
        r = client.get(path, headers=H1)
        assert r.status_code == 502 and r.json() == {"detail": "enterprise_unavailable"}


def test_router_shares_the_process_wide_client(monkeypatch, tmp_path, small_seed):
    client_mod.reset_client_cache()
    seed = tmp_path / "seed.json"
    seed.write_text(small_seed.model_dump_json(), encoding="utf-8")
    monkeypatch.delenv("KIRCHHOFF_ENTERPRISE_URL", raising=False)
    monkeypatch.setenv("KIRCHHOFF_ENTERPRISE_SEED", str(seed))
    client = _client(None)
    assert len(client.get(PATHS[0], headers=H1).json()) == 3
    client_mod.make_enterprise_client().create_pr("u1", "hall-b", "x-r2", LINES, idempotency_key="k")  # WS2's P4
    assert any(p["project_id"] == "hall-b" for p in client.get(PATHS[1], headers=H1).json())
    client_mod.reset_client_cache()


def test_p2_create_app_mounts_the_proxy(monkeypatch):
    pytest.importorskip("kirchhoff.api.deps")  # WS2 P2 Task 12
    monkeypatch.setenv("KIRCHHOFF_FAKES", "1")
    monkeypatch.setenv("KIRCHHOFF_BLOBS", "memory")
    from kirchhoff.api.app import create_app

    app = create_app(store=MemoryStore(), verify_token=lambda t: "u1")
    assert set(PATHS) <= {getattr(r, "path", "") for r in app.routes}
