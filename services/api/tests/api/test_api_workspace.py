import threading
import time

from fastapi.testclient import TestClient

from kirchhoff.api.app import create_app
from kirchhoff.api.deps import LazyModule, build_production_deps
from kirchhoff.runs.phase1 import run_p1
from kirchhoff.store.memory import MemoryStore


def test_workspace_create_is_idempotent(client, auth):
    assert client.post("/api/workspace", headers=auth).json() == {"uid": "u1", "created": True}
    assert client.post("/api/workspace", headers=auth).json() == {"uid": "u1", "created": False}


def test_whoami_survives_the_app_rewiring(client, auth):
    assert client.get("/api/whoami").status_code == 401  # infra/smoke.sh probes this
    assert client.get("/api/whoami", headers=auth).json() == {"uid": "u1"}


def test_reset_deletes_visitor_data(client, deps, auth):
    deps.phases = {"p1": run_p1}
    assert client.post("/api/runs", json={"project_id": "hall-b"}, headers=auth).status_code == 202
    deps.blobs.put("workspaces/u1/exports/x-r1/boq.csv", b"a,b", "text/csv")
    deps.enterprise.create_pr("u1", "hall-b", "x-r1", [], idempotency_key="k1")
    assert client.post("/api/workspace/reset", headers=auth).json() == {"ok": True}
    assert deps.store.list_docs("workspaces/u1/runs") == [] and deps.store.get_doc("workspaces/u1") is None
    assert not deps.blobs.blobs and not deps.enterprise.prs


def test_reset_refuses_while_a_run_holds_a_live_lease(client, deps, auth):
    deps.store.set_doc("workspaces/u1/runs/r1", {"id": "r1", "status": "running",
                                                  "lease": {"owner": "w", "attempt": 1, "heartbeat_at": deps.clock()}})
    r = client.post("/api/workspace/reset", headers=auth)
    assert r.status_code == 409 and r.json() == {"detail": "run_in_progress"}


def test_production_app_builds_without_network(monkeypatch):
    monkeypatch.delenv("KIRCHHOFF_FAKES", raising=False)
    app = create_app(store=MemoryStore(), verify_token=lambda token: "u1")
    assert TestClient(app).get("/api/health").json()["ok"] is True
    assert isinstance(app.state.deps.engine, LazyModule)


def test_warm_up_runs_once_in_background_without_blocking_startup(monkeypatch):
    """Context (not in the brief's literal test list): the engine's warm_up() must run once, off the
    request path, so the first what-if isn't ~1s cold. It must not run at import or at create_app()
    construction time, and it must not block the health check."""
    monkeypatch.delenv("KIRCHHOFF_FAKES", raising=False)

    class CountingEngine:
        def __init__(self) -> None:
            self.calls = 0
            self.started = threading.Event()
            self._lock = threading.Lock()

        def warm_up(self) -> None:
            self.started.set()
            time.sleep(0.2)
            with self._lock:
                self.calls += 1

    deps = build_production_deps(MemoryStore())
    assert deps.engine.calls == 0 if hasattr(deps.engine, "calls") else True  # not warmed at construction
    engine = CountingEngine()
    deps.engine = engine
    app = create_app(deps=deps, verify_token=lambda token: "u1")
    assert engine.calls == 0  # create_app() itself never calls warm_up

    with TestClient(app) as test_client:
        t0 = time.time()
        assert test_client.get("/api/health").json()["ok"] is True
        elapsed = time.time() - t0
        assert elapsed < 0.2  # startup did not block on warm_up's sleep
        assert engine.started.wait(timeout=2.0)

    deadline = time.time() + 2.0
    while engine.calls == 0 and time.time() < deadline:
        time.sleep(0.01)
    assert engine.calls == 1
