import time
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.formparsers import MultiPartException

from kirchhoff.agents.copilot import (BadRevisionRef, RevisionNotFound, answer_voice, call_with_timeout, explain_text,
                                      load_revision)
from kirchhoff.engine.whatif import PARAM_BOUNDS
from kirchhoff.runs.deps import Deps

from .errors import err

VOICE_MIME = {"audio/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/mpeg"}
VOICE_MAX_BYTES = 2_000_000
# Fix round 1, Important #1: allowance above VOICE_MAX_BYTES for multipart boundaries/headers and the
# revision_ref field, so a genuinely oversize audio part is rejected by its declared Content-Length before
# any parsing starts, and (if the client lies about Content-Length) by max_part_size during parsing.
VOICE_CONTENT_LENGTH_OVERHEAD = 65_536

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
        lo, hi = PARAM_BOUNDS[body.param]
        if not lo <= body.value <= hi:
            return err(422, "invalid_value")  # ruling P2-R17: an out-of-range what-if value, checked up front
        # Task 15 residual fix (b): deps.erp() is fetched in its own call_with_timeout/except pair so a
        # plain ValueError it might raise (HttpEnterpriseClient on a sandbox 422, unrelated to the what-if
        # value) is never caught by the engine call's `except ValueError` below and mislabelled invalid_value.
        # Fix round 1, Minor: both calls share one deadline instead of each getting a fresh WHAT_IF_TIMEOUT_S,
        # which could otherwise sum to twice the budget.
        deadline = time.monotonic() + WHAT_IF_TIMEOUT_S
        try:
            erp = call_with_timeout(deps.erp, max(0.0, deadline - time.monotonic()))
        except FuturesTimeout:
            return err(504, "timeout")
        except EnterpriseUnavailable:
            return err(503, "enterprise_unavailable")
        try:
            res = call_with_timeout(lambda: deps.engine.what_if(deps.scenario(), model, body.param, body.value,
                                                                body.revision_ref, erp),
                                    max(0.0, deadline - time.monotonic()))
        except FuturesTimeout:
            return err(504, "timeout")
        except ValidationError:
            raise  # a server bug (e.g. a malformed engine/erp record), never the caller's what-if value
        except ValueError:
            return err(422, "invalid_value")  # ruling P2-R17: the engine itself rejected the what-if value
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
    async def voice(request: Request, uid: str = Depends(current_uid)):
        # Fix round 1, Important #1: FastAPI/Starlette parse the whole multipart body before a route's own
        # File(...)/Form(...) dependencies run, with no cap by default -- on Cloud Run the temp filesystem is
        # RAM, so an unbounded upload is a real resource risk. A declared Content-Length over budget is
        # rejected before parsing starts at all; max_part_size then bounds parsing itself against a client
        # that lies about a small Content-Length but sends a large body.
        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > VOICE_MAX_BYTES + VOICE_CONTENT_LENGTH_OVERHEAD:
                    return err(413, "audio_too_large")
            except ValueError:
                pass
        try:
            form = await request.form(max_part_size=VOICE_MAX_BYTES + 1)
        except MultiPartException:
            return err(413, "audio_too_large")
        audio = form.get("audio")
        if audio is None or not hasattr(audio, "read"):
            return err(422, "audio_required")
        data = await audio.read(VOICE_MAX_BYTES + 1)
        if len(data) > VOICE_MAX_BYTES:
            return err(413, "audio_too_large")
        revision_ref = form.get("revision_ref") or "seed:hall-a@r2"
        mime = (audio.content_type or "").split(";")[0].strip().lower()
        if mime == "audio/x-wav":
            mime = "audio/wav"  # Minor: Vertex expects the canonical mime type
        if mime not in VOICE_MIME:
            return err(415, "unsupported_audio")
        try:
            return await run_in_threadpool(answer_voice, deps, uid, revision_ref, data, mime)
        except RevisionNotFound:
            return err(404, "revision_not_found")
        except BadRevisionRef:
            return err(422, "bad_revision_ref")
        except EnterpriseUnavailable:
            return err(503, "enterprise_unavailable")
        except FuturesTimeout:
            return err(504, "timeout")

    return router
