import inspect

import httpx
import pytest
from fastapi.testclient import TestClient

from kirchhoff.contracts import PRLine
from kirchhoff.enterprise.app import create_enterprise_app
from kirchhoff.enterprise.client import (EnterpriseUnavailable, HttpEnterpriseClient, LocalEnterpriseClient,
                                         make_enterprise_client, reset_client_cache)
from kirchhoff.enterprise.sandbox import NotFound

LINES = [PRLine(material_id="TX-3150", description="TX-3150 item", qty=6, unit_price=100.0, lead_time_weeks=12)]


@pytest.fixture
def http_client(sandbox):
    return HttpEnterpriseClient("http://testserver", token=lambda: "test-token",
                                http=TestClient(create_enterprise_app(sandbox)))


def _mock(handler) -> httpx.Client:
    return httpx.Client(base_url="http://sandbox", transport=httpx.MockTransport(handler))


def test_service_health_reports_the_sandbox_label(sandbox):
    body = TestClient(create_enterprise_app(sandbox)).get("/health").json()
    assert body["ok"] is True and body["label"] == "sandbox (simulated)" and body["materials"] == 3


def test_http_client_round_trip(http_client):
    assert [m.id for m in http_client.list_materials()] == ["BW-1600", "TX-2500", "TX-3150"]
    a = http_client.create_pr("u1", "hall-b", "x-r2", LINES, idempotency_key="x:x-r2:Tapti Transformers")
    assert http_client.create_pr("u1", "hall-b", "x-r2", LINES, idempotency_key="x:x-r2:Tapti Transformers").id == a.id
    http_client.set_pr_status("u1", a.id, "blocked")
    assert {p.id: p.status for p in http_client.list_prs("u1")}[a.id] == "blocked"
    assert http_client.set_opportunity_stage("u1", "opp-hall-b", "Design approved").stage == "Design approved"
    assert {o.id: o.stage for o in http_client.list_opportunities("u1")}["opp-hall-b"] == "Design approved"
    assert {o.id: o.stage for o in http_client.list_opportunities("u2")}["opp-hall-b"] == "Design in progress"
    http_client.reset_visitor("u1")
    assert [p.id for p in http_client.list_prs("u1")] == ["PR-2026-0142"]


def test_http_client_maps_404_and_422(http_client):
    with pytest.raises(NotFound):
        http_client.set_pr_status("u1", "PR-2026-9999", "blocked")
    with pytest.raises(ValueError):
        http_client.set_opportunity_stage("u1", "opp-hall-b", "Shipped")


def test_http_client_sends_the_id_token_retries_once_then_gives_up():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("authorization"))
        return httpx.Response(503, json={"detail": "cold start"})

    client = HttpEnterpriseClient("http://sandbox", token=lambda: "tok", retries=1, http=_mock(handler))
    with pytest.raises(EnterpriseUnavailable):
        client.list_materials()
    assert seen == ["Bearer tok", "Bearer tok"]


def test_http_client_recovers_after_a_transport_error():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json=[])

    client = HttpEnterpriseClient("http://sandbox", token=lambda: "tok", http=_mock(handler))
    assert client.list_materials() == [] and calls["n"] == 2


def test_make_enterprise_client_modes(tmp_path, small_seed):
    reset_client_cache()
    seed_file = tmp_path / "seed.json"
    seed_file.write_text(small_seed.model_dump_json(), encoding="utf-8")
    env = {"KIRCHHOFF_ENTERPRISE_SEED": str(seed_file)}
    local = make_enterprise_client(env)
    assert isinstance(local, LocalEnterpriseClient) and make_enterprise_client(env) is local
    assert [m.id for m in local.list_materials()] == ["BW-1600", "TX-2500", "TX-3150"]
    remote = make_enterprise_client({"KIRCHHOFF_ENTERPRISE_URL": "https://kirchhoff-enterprise.example.run.app"})
    assert isinstance(remote, HttpEnterpriseClient)  # constructed without any network call
    broken = make_enterprise_client({"KIRCHHOFF_ENTERPRISE_SEED": str(tmp_path / "missing.json")})
    assert isinstance(broken, LocalEnterpriseClient)  # falls back to erp_seed.yaml; never raises
    reset_client_cache()


def test_clients_match_the_ws2_enterprise_protocol():
    ports = pytest.importorskip("kirchhoff.agents.ports")
    names = [n for n in vars(ports.EnterpriseClient) if not n.startswith("_")]  # grows with WS2's protocol
    assert {"list_materials", "create_pr", "set_pr_status", "set_opportunity_stage", "reset_visitor"} <= set(names)
    for name in names:
        want = list(inspect.signature(getattr(ports.EnterpriseClient, name)).parameters)
        for cls in (LocalEnterpriseClient, HttpEnterpriseClient):
            assert list(inspect.signature(getattr(cls, name)).parameters) == want, (cls.__name__, name)


def test_http_client_creates_visitor_opportunities(http_client):
    from kirchhoff.contracts import Opportunity

    opp = Opportunity(id="opp-em-x", account="Suryodaya Renewables", name="Enquiry", stage="Qualification", value=0.0)
    assert http_client.create_opportunity("u1", opp) == opp
    assert "opp-em-x" in {o.id for o in http_client.list_opportunities("u1")}
    with pytest.raises(ValueError):
        http_client.create_opportunity("u1", opp.model_copy(update={"id": "opp-hall-b"}))
