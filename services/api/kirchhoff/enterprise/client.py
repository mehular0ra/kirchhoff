"""Enterprise clients (ruling W4). WS2 calls make_enterprise_client() from build_production_deps (P2 Task 12); the
/api/enterprise proxy calls it too and gets the same instance. Nothing here touches the network at construction."""
import logging
import os
import threading
import time
from typing import Any, Callable, Mapping
from urllib.parse import quote

import httpx

from kirchhoff.contracts import CrmOverlay, Material, Opportunity, PRLine, PurchaseRequisition
from kirchhoff.store.memory import MemoryStore

from .model import FALLBACK_OPPORTUNITIES, EnterpriseSeed, fallback_seed, load_enterprise_seed
from .paths import enterprise_seed_path, scenarios_dir
from .sandbox import NotFound, Sandbox

log = logging.getLogger("kirchhoff")


class EnterpriseUnavailable(RuntimeError):
    """The sandbox did not answer in time, answered 5xx after retries, or refused the caller (401/403)."""


class LocalEnterpriseClient:
    """In-process sandbox: tests, local development and KIRCHHOFF_ENTERPRISE=firestore."""

    def __init__(self, sandbox: Sandbox) -> None:
        self.sandbox = sandbox

    def list_materials(self) -> list[Material]:
        return self.sandbox.list_materials()

    def list_prs(self, uid: str | None) -> list[PurchaseRequisition]:
        return self.sandbox.list_prs(uid)

    def create_pr(self, uid, project_id, revision, lines, idempotency_key) -> PurchaseRequisition:
        return self.sandbox.create_pr(uid, project_id, revision, list(lines), idempotency_key)

    def set_pr_status(self, uid, pr_id, status) -> None:
        self.sandbox.set_pr_status(uid, pr_id, status)

    def list_opportunities(self, uid: str | None) -> list[Opportunity]:
        return self.sandbox.list_opportunities(uid)

    def set_opportunity_stage(self, uid, opportunity_id, stage) -> CrmOverlay:
        return self.sandbox.set_opportunity_stage(uid, opportunity_id, stage)

    def create_opportunity(self, uid, opportunity) -> Opportunity:
        return self.sandbox.create_opportunity(uid, Opportunity.model_validate(opportunity))

    def reset_visitor(self, uid) -> None:
        self.sandbox.reset_visitor(uid)


class GoogleIdTokens:
    """Google-signed ID tokens for Cloud Run service-to-service calls (metadata server on Cloud Run), cached."""

    def __init__(self, audience: str, ttl_s: float = 3000.0) -> None:
        self.audience, self.ttl_s = audience, ttl_s
        self._token: str | None = None
        self._at = 0.0
        self._lock = threading.Lock()

    def __call__(self) -> str:
        with self._lock:
            if self._token is None or time.monotonic() - self._at > self.ttl_s:
                import google.auth.transport.requests
                import google.oauth2.id_token

                self._token = google.oauth2.id_token.fetch_id_token(google.auth.transport.requests.Request(),
                                                                    self.audience)
                self._at = time.monotonic()
            return self._token


class HttpEnterpriseClient:
    """kirchhoff-enterprise over HTTPS. 3 s per attempt and one retry keep request-path calls under 10 s."""

    def __init__(self, base_url: str, token: Callable[[], str] | None = None, timeout_s: float = 3.0,
                 retries: int = 1, http: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token or GoogleIdTokens(self.base_url)
        self._timeout = httpx.Timeout(timeout_s, connect=min(1.5, timeout_s))
        self._retries = retries
        self._http = http
        self._lock = threading.Lock()

    def _client(self) -> httpx.Client:
        with self._lock:
            if self._http is None:
                self._http = httpx.Client(base_url=self.base_url, timeout=self._timeout)
            return self._http

    def _call(self, method: str, path: str, *, params: dict | None = None, body: dict | None = None) -> Any:
        last: object = None
        for _ in range(1 + self._retries):
            try:
                token = self._token()
            except Exception as exc:
                raise EnterpriseUnavailable(f"no ID token for {self.base_url}: {type(exc).__name__}") from exc
            try:
                r = self._client().request(method, path, params=params, json=body,
                                           headers={"Authorization": f"Bearer {token}"})
            except httpx.HTTPError as exc:  # connect/read timeouts, refused connections
                last = exc
                continue
            if r.status_code == 404:
                raise NotFound(r.json().get("detail", path))
            if r.status_code == 422:
                raise ValueError(str(r.json().get("detail", "invalid request")))
            if r.status_code >= 500:
                last = f"HTTP {r.status_code}"
                continue
            if r.status_code >= 400:
                raise EnterpriseUnavailable(f"{method} {path} -> HTTP {r.status_code}")
            return r.json()
        raise EnterpriseUnavailable(f"{method} {path} failed after {1 + self._retries} attempts: {last!r}")

    def list_materials(self) -> list[Material]:
        return [Material.model_validate(x) for x in self._call("GET", "/erp/materials")]

    def list_prs(self, uid: str | None) -> list[PurchaseRequisition]:
        data = self._call("GET", "/erp/prs", params={"uid": uid} if uid else None)
        return [PurchaseRequisition.model_validate(x) for x in data]

    def create_pr(self, uid, project_id, revision, lines, idempotency_key) -> PurchaseRequisition:
        body = {"uid": uid, "project_id": project_id, "revision": revision,
                "lines": [PRLine.model_validate(x).model_dump(mode="json") for x in lines],
                "idempotency_key": idempotency_key}
        return PurchaseRequisition.model_validate(self._call("POST", "/erp/prs", body=body))

    def set_pr_status(self, uid, pr_id, status) -> None:
        self._call("POST", f"/erp/prs/{quote(pr_id, safe='')}/status", body={"uid": uid, "status": status})

    def list_opportunities(self, uid: str | None) -> list[Opportunity]:
        data = self._call("GET", "/crm/opportunities", params={"uid": uid} if uid else None)
        return [Opportunity.model_validate(x) for x in data]

    def set_opportunity_stage(self, uid, opportunity_id, stage) -> CrmOverlay:
        data = self._call("POST", f"/crm/opportunities/{quote(opportunity_id, safe='')}/stage",
                          body={"uid": uid, "stage": stage})
        return CrmOverlay.model_validate(data)

    def create_opportunity(self, uid, opportunity) -> Opportunity:
        body = {"uid": uid, "opportunity": Opportunity.model_validate(opportunity).model_dump(mode="json")}
        return Opportunity.model_validate(self._call("POST", "/crm/opportunities", body=body))

    def reset_visitor(self, uid) -> None:
        self._call("DELETE", f"/visitors/{quote(uid, safe='')}")

    def health(self) -> dict:
        return self._call("GET", "/health")


class _LazyFirestore:
    """Creates the Firestore client on first use (no network at construction)."""

    def __init__(self) -> None:
        self._store = None
        self._lock = threading.Lock()

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        with self._lock:
            if self._store is None:
                from kirchhoff.store.firestore import FirestoreStore
                self._store = FirestoreStore()
        return getattr(self._store, name)


_CLIENTS: dict[tuple[str, str], Any] = {}
_CLIENTS_LOCK = threading.Lock()


def default_seed(env: Mapping[str, str]) -> EnterpriseSeed:
    path = env.get("KIRCHHOFF_ENTERPRISE_SEED") or str(enterprise_seed_path())
    try:
        return load_enterprise_seed(path)
    except (OSError, ValueError) as exc:
        log.warning("enterprise seed %s unavailable (%s); using the Hall A ERP only", path, type(exc).__name__)
        return fallback_seed(scenarios_dir() / "hall_a" / "erp_seed.yaml")


def _memory_client(env: Mapping[str, str]) -> LocalEnterpriseClient:
    sandbox = Sandbox(MemoryStore())
    try:
        sandbox.load_seed(default_seed(env))
    except Exception as exc:  # a broken seed must never stop the API from starting
        log.warning("enterprise seed rejected (%s); starting with an empty ERP", type(exc).__name__)
        sandbox.load_seed(EnterpriseSeed(materials=[], opportunities=list(FALLBACK_OPPORTUNITIES)))
    return LocalEnterpriseClient(sandbox)


def make_enterprise_client(env: Mapping[str, str] | None = None):
    """Ruling W4: HTTP when KIRCHHOFF_ENTERPRISE_URL is set, else an in-process sandbox (memory by default,
    KIRCHHOFF_ENTERPRISE=firestore for the real seed). One instance per mode per process."""
    env = os.environ if env is None else env
    url = (env.get("KIRCHHOFF_ENTERPRISE_URL") or "").strip()
    mode = "http" if url else (env.get("KIRCHHOFF_ENTERPRISE") or "memory")
    key = (mode, url or env.get("KIRCHHOFF_ENTERPRISE_SEED", ""))
    with _CLIENTS_LOCK:
        if key not in _CLIENTS:
            if mode == "http":
                _CLIENTS[key] = HttpEnterpriseClient(url)
            elif mode == "firestore":
                _CLIENTS[key] = LocalEnterpriseClient(Sandbox(_LazyFirestore()))
            else:
                _CLIENTS[key] = _memory_client(env)
        return _CLIENTS[key]


def reset_client_cache() -> None:
    with _CLIENTS_LOCK:
        _CLIENTS.clear()
