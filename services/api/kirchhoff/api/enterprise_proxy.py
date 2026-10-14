"""/api/enterprise/* (spec §7; interfaces HTTP table): the UI never calls the sandbox directly. Read-only views for
the signed-in visitor; the sandbox is the source of truth (ruling W5). P2's create_app mounts this router."""
import logging
from typing import Callable

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

log = logging.getLogger("kirchhoff")


def make_router(store, current_uid, client=None) -> APIRouter:
    """`store` keeps P2's create_app signature; `client` is injectable for tests (default: the shared client)."""
    router = APIRouter()
    holder = {"client": client}

    def enterprise():
        if holder["client"] is None:
            from kirchhoff.enterprise.client import make_enterprise_client
            holder["client"] = make_enterprise_client()
        return holder["client"]

    def respond(fn: Callable[[], list]):
        try:
            return fn()
        except Exception as exc:  # the UI falls back to /demo/integrations.json
            log.warning("enterprise proxy failed: %s", type(exc).__name__)
            return JSONResponse(status_code=502, content={"detail": "enterprise_unavailable"})

    @router.get("/api/enterprise/erp/materials")
    def materials(uid: str = Depends(current_uid)):
        return respond(lambda: [m.model_dump(mode="json") for m in enterprise().list_materials()])

    @router.get("/api/enterprise/erp/prs")
    def prs(uid: str = Depends(current_uid)):
        return respond(lambda: [p.model_dump(mode="json") for p in enterprise().list_prs(uid)])

    @router.get("/api/enterprise/crm/opportunities")
    def opportunities(uid: str = Depends(current_uid)):
        return respond(lambda: [o.model_dump(mode="json") for o in enterprise().list_opportunities(uid)])

    return router
