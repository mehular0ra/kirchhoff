from fastapi.testclient import TestClient

from kirchhoff.agents.docs_export import BlobExporter
from kirchhoff.api.app import create_app
from kirchhoff.api.deps import build_production_deps
from kirchhoff.runs.blobs import MemoryBlobStore, SigningUnavailable
from kirchhoff.runs.revisions import latest_revision
from kirchhoff.store.memory import MemoryStore


def _to_review(client, auth) -> str:
    rid = client.post("/api/runs", json={"project_id": "hall-b", "autonomy": "auto"}, headers=auth).json()["run_id"]
    return rid


def test_exports_are_written_and_served_by_signed_url(client, deps, auth):
    deps.exporter = BlobExporter(deps.blobs)
    rid = _to_review(client, auth)
    rev = latest_revision(deps.store, "u1", rid)["id"]
    events = deps.store.list_docs(f"workspaces/u1/runs/{rid}/events")
    exports = [e["payload"] for e in events if e["kind"] == "artifact" and e["payload"]["type"] == "export"]
    assert [e["ref"] for e in exports] == [f"exports/{rev}/calc-report.pdf", f"exports/{rev}/boq.csv"]
    r = client.get(f"/api/files/exports/{rev}/calc-report.pdf", headers=auth, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].startswith(
        f"https://storage.example.test/workspaces/u1/exports/{rev}/calc-report.pdf")
    model = client.get(f"/api/files/revisions/{rev}/model.json", headers=auth, follow_redirects=False)
    assert model.status_code == 302
    as_json = client.get(f"/api/files/exports/{rev}/boq.csv?redirect=0", headers=auth)
    assert as_json.status_code == 200 and as_json.json()["url"].startswith(
        f"https://storage.example.test/workspaces/u1/exports/{rev}/boq.csv") and as_json.json()["expires_in"] == 600


def test_unsigned_blob_store_serves_bytes_inline(client, deps, auth):
    deps.blobs = MemoryBlobStore(public_base=None)  # local KIRCHHOFF_FAKES=1 / KIRCHHOFF_BLOBS=memory
    deps.blobs.put("workspaces/u1/revisions/x-r1/model.json", b'{"racks": []}', "application/json")
    for q in ("", "?redirect=0"):
        r = client.get(f"/api/files/revisions/x-r1/model.json{q}", headers=auth, follow_redirects=False)
        assert r.status_code == 200 and r.headers["x-kirchhoff-inline"] == "1" and r.json() == {"racks": []}


def test_files_are_scoped_and_validated(client, deps, auth):
    deps.blobs.put("workspaces/u1/exports/x-r1/boq.csv", b"a", "text/csv")
    assert client.get("/api/files/exports/x-r1/boq.csv", headers=auth, follow_redirects=False).status_code == 302
    other = TestClient(create_app(deps=deps, verify_token=lambda t: "u2"))
    assert other.get("/api/files/exports/x-r1/boq.csv", headers=auth, follow_redirects=False).status_code == 404
    for bad in ["exports/../u2/boq.csv", "secrets/x/y", "exports/x-r1"]:
        assert client.get(f"/api/files/{bad}", headers=auth, follow_redirects=False).status_code == 404


def test_traversal_guard_rejects_dot_segments_and_backslashes(client, deps, auth):
    # httpx normalises literal ".." path segments before they ever reach the server, so a naive test
    # (asserting on "exports/../u2/boq.csv") can pass even with the `".." in path` guard removed. Plant
    # a literal blob key containing "..", then exercise the raw, already-percent-encoded/backslash
    # forms an attacker (or a buggy proxy) could actually deliver, which httpx does NOT normalise away.
    deps.blobs.put("workspaces/u1/exports/../boq.csv", b"x", "text/csv")
    for bad in ["exports/%2e%2e/boq.csv", "exports/..%2fx-r1/boq.csv", "/exports/x-r1/boq.csv",
                "exports%5cx-r1%5cboq.csv", "exports/x-r1%5c..%5cboq.csv", "secrets/x/y", "exports/x-r1"]:
        assert client.get(f"/api/files/{bad}", headers=auth, follow_redirects=False).status_code == 404


def test_build_production_deps_wires_a_blob_exporter():
    deps = build_production_deps(MemoryStore())
    assert isinstance(deps.exporter, BlobExporter)


def test_signing_unavailable_is_a_not_implemented_error():
    assert issubclass(SigningUnavailable, NotImplementedError)
    blobs = MemoryBlobStore(public_base=None)
    blobs.put("workspaces/u1/x", b"a", "text/plain")
    try:
        blobs.signed_url("workspaces/u1/x")
    except SigningUnavailable:
        pass
    else:
        raise AssertionError("expected SigningUnavailable")


def test_hello_route_is_gone_and_whoami_stays(client, auth):
    assert client.post("/api/hello-run", headers=auth).status_code == 404
    assert client.get("/api/whoami").status_code == 401
    assert client.get("/api/whoami", headers=auth).json() == {"uid": "u1"}
