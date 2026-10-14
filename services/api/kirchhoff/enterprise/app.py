"""kirchhoff-enterprise (spec §7): the ERP/CRM sandbox as its own Cloud Run service, same image as kirchhoff-api.
Cloud Run IAM admits only the runtime service account (ruling W2); requests carry the visitor uid.
Sandbox (simulated): every record is fictional."""
import os
from typing import Callable

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from kirchhoff.contracts import Opportunity, PRLine

from .model import SANDBOX_LABEL
from .sandbox import NotFound, Sandbox


class CreatePr(BaseModel):
    uid: str
    project_id: str
    revision: str
    lines: list[PRLine]
    idempotency_key: str


class SetStatus(BaseModel):
    uid: str
    status: str


class SetStage(BaseModel):
    uid: str
    stage: str


class CreateOpportunity(BaseModel):
    uid: str
    opportunity: Opportunity


def _guard(fn: Callable[[], object]):
    try:
        return fn()
    except NotFound as exc:
        return JSONResponse(status_code=404, content={"detail": f"not_found: {exc.args[0] if exc.args else ''}"})
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc)})


def create_enterprise_app(sandbox: Sandbox | None = None) -> FastAPI:
    if sandbox is None:
        from kirchhoff.store.firestore import FirestoreStore
        sandbox = Sandbox(FirestoreStore())
    app = FastAPI(title="Kirchhoff enterprise sandbox (simulated)")

    @app.get("/health")
    def health() -> dict:
        meta = sandbox.meta()
        return {"ok": True, "service": "kirchhoff-enterprise", "label": SANDBOX_LABEL,
                "version": os.environ.get("K_REVISION", "dev"), "seed_hash": meta.get("hash"),
                "materials": meta.get("materials", 0)}

    @app.get("/erp/materials")
    def materials():
        return [m.model_dump(mode="json") for m in sandbox.list_materials()]

    @app.get("/erp/prs")
    def prs(uid: str | None = Query(default=None)):
        return _guard(lambda: [p.model_dump(mode="json") for p in sandbox.list_prs(uid)])

    @app.post("/erp/prs")
    def create_pr(body: CreatePr):
        return _guard(lambda: sandbox.create_pr(body.uid, body.project_id, body.revision, body.lines,
                                                body.idempotency_key).model_dump(mode="json"))

    @app.post("/erp/prs/{pr_id}/status")
    def set_status(pr_id: str, body: SetStatus):
        def run() -> dict:
            sandbox.set_pr_status(body.uid, pr_id, body.status)
            return {"ok": True}
        return _guard(run)

    @app.get("/crm/opportunities")
    def opportunities(uid: str | None = Query(default=None)):
        return _guard(lambda: [o.model_dump(mode="json") for o in sandbox.list_opportunities(uid)])

    @app.post("/crm/opportunities/{opportunity_id}/stage")
    def set_stage(opportunity_id: str, body: SetStage):
        return _guard(lambda: sandbox.set_opportunity_stage(body.uid, opportunity_id, body.stage)
                      .model_dump(mode="json"))

    @app.post("/crm/opportunities")
    def create_opportunity(body: CreateOpportunity):
        return _guard(lambda: sandbox.create_opportunity(body.uid, body.opportunity).model_dump(mode="json"))

    @app.delete("/visitors/{uid}")
    def reset(uid: str):
        return _guard(lambda: {"ok": True, "deleted": sandbox.reset_visitor(uid)})

    app.state.sandbox = sandbox
    return app
