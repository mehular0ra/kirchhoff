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


def test_hello_run_sets_failed_status_on_error(monkeypatch):
    """Test that a store failure during hello-run sets status to 'failed' instead of leaving it 'running'."""
    monkeypatch.setenv("KIRCHHOFF_HELLO_INTERVAL_S", "0.01")

    class FailingStore:
        """Store that raises on batch_set to simulate write failures."""
        def __init__(self):
            self.docs = {}

        def set_doc(self, path: str, data: dict) -> None:
            self.docs[path] = data

        def update_doc(self, path: str, data: dict) -> None:
            self.docs.setdefault(path, {}).update(data)

        def get_doc(self, path: str) -> dict | None:
            return self.docs.get(path)

        def batch_set(self, items: list[tuple[str, dict]]) -> None:
            raise RuntimeError("Store write failed")

        def list_docs(self, collection_path: str) -> list[dict]:
            return []

    store = FailingStore()
    client = TestClient(create_app(store=store, verify_token=lambda t: "u1"))
    r = client.post("/api/hello-run", headers={"Authorization": "Bearer x"})
    assert r.status_code == 202
    run_id = r.json()["run_id"]

    # Wait for background thread to fail and update status
    for _ in range(100):
        run = store.get_doc(f"workspaces/u1/runs/{run_id}")
        if run and run["status"] == "failed":
            break
        time.sleep(0.02)

    assert run["status"] == "failed"
    assert "RuntimeError: Store write failed" in run["error"]
    assert run.get("finished_at") is not None
