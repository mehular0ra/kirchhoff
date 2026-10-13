import time

from fastapi.testclient import TestClient

from kirchhoff.api.app import create_app
from kirchhoff.store.memory import MemoryStore


def test_health_needs_no_auth():
    client = TestClient(create_app(store=MemoryStore(), verify_token=lambda t: "u1"))
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_hello_run_rejects_missing_token():
    client = TestClient(create_app(store=MemoryStore(), verify_token=lambda t: "u1"))
    assert client.post("/api/hello-run").status_code == 401


def test_hello_run_streams_events(monkeypatch):
    monkeypatch.setenv("KIRCHHOFF_HELLO_INTERVAL_S", "0.01")
    store = MemoryStore()
    client = TestClient(create_app(store=store, verify_token=lambda t: "u1"))
    r = client.post("/api/hello-run", headers={"Authorization": "Bearer x"})
    assert r.status_code == 202
    run_id = r.json()["run_id"]
    for _ in range(100):
        run = store.get_doc(f"workspaces/u1/runs/{run_id}")
        if run and run["status"] == "done":
            break
        time.sleep(0.02)
    events = store.list_docs(f"workspaces/u1/runs/{run_id}/events")
    assert run["status"] == "done"
    assert len(events) == 5
