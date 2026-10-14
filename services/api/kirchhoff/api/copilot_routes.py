from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from kirchhoff.agents.copilot import (BadRevisionRef, RevisionNotFound, answer_voice, call_with_timeout, explain_text,
                                      load_revision)
from kirchhoff.runs.deps import Deps

from .errors import err

VOICE_MIME = {"audio/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/mpeg"}
VOICE_MAX_BYTES = 2_000_000

try:
    from kirchhoff.enterprise.client import EnterpriseUnavailable  # WS4-owned module
except ImportError:
    class EnterpriseUnavailable(Exception):
        """Placeholder when kirchhoff.enterprise.client is unavailable (never actually raised)."""

WHAT_IF_TIMEOUT_S = 8.0


class WhatIfBody(BaseModel):
    revision_ref: str
    param: Literal["rack_kw", "liquid_fraction", "dv_limit_pct", "tx_loading_cap_pct"]
    value: float


class ExplainBody(BaseModel):
    revision_ref: str
    finding_id: str


def make_router(deps: Deps, current_uid) -> APIRouter:
    router = APIRouter()

    def load(uid: str, ref: str):
        try:
            return load_revision(deps, uid, ref), None
        except RevisionNotFound:
            return None, err(404, "revision_not_found")
        except BadRevisionRef:
            return None, err(422, "bad_revision_ref")

    @router.post("/api/what-if")
    def what_if(body: WhatIfBody, uid: str = Depends(current_uid)):
        loaded, error = load(uid, body.revision_ref)
        if error:
            return error
        model, _ = loaded
        try:
            res = call_with_timeout(lambda: deps.engine.what_if(deps.scenario(), model, body.param, body.value,
                                                                body.revision_ref, deps.erp()), WHAT_IF_TIMEOUT_S)
        except FuturesTimeout:
            return err(504, "timeout")
        except ValueError:
            return err(422, "invalid_value")  # ruling P2-R17: an out-of-range what-if param, not a server error
        except EnterpriseUnavailable:
            return err(503, "enterprise_unavailable")
        return res.model_dump(mode="json")

    @router.post("/api/explain")
    def explain(body: ExplainBody, uid: str = Depends(current_uid)):
        loaded, error = load(uid, body.revision_ref)
        if error:
            return error
        model, findings = loaded
        finding = next((f for f in findings if f.id == body.finding_id), None)
        if finding is None:
            return err(404, "finding_not_found")
        return {"text": explain_text(deps, model, finding)}

    @router.post("/api/voice")
    async def voice(audio: UploadFile = File(...), revision_ref: str = Form("seed:hall-a@r2"),
                    uid: str = Depends(current_uid)):
        data = await audio.read()
        if len(data) > VOICE_MAX_BYTES:
            return err(413, "audio_too_large")
        mime = (audio.content_type or "").split(";")[0].strip().lower()
        if mime not in VOICE_MIME:
            return err(415, "unsupported_audio")
        try:
            return await run_in_threadpool(answer_voice, deps, uid, revision_ref, data, mime)
        except RevisionNotFound:
            return err(404, "revision_not_found")
        except ValueError:
            return err(422, "bad_revision_ref")
        except FuturesTimeout:
            return err(504, "timeout")

    return router
