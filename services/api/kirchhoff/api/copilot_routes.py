import time
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.formparsers import FormData, FormParser, MultiPartException, MultiPartParser, parse_options_header

from kirchhoff.agents.copilot import (BadRevisionRef, RevisionNotFound, answer_voice, call_with_timeout, explain_text,
                                      load_revision)
from kirchhoff.engine.whatif import PARAM_BOUNDS
from kirchhoff.runs.deps import Deps
from kirchhoff.runs.revisions import with_citation_boxes

from .errors import err

VOICE_MIME = {"audio/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/mpeg"}
VOICE_MAX_BYTES = 2_000_000
# Fix round 1, Important #1: allowance above VOICE_MAX_BYTES for multipart boundaries/headers and the
# revision_ref field, so a genuinely oversize audio part is rejected by its declared Content-Length before
# any parsing starts.
# Fix round 2: Starlette 1.8.0's `max_part_size` does NOT bound FILE parts (only non-file form fields --
# formparsers.py's `on_part_data` only checks it `if self._current_part.file is None`), so it gave no real
# protection against a client that lies about a small Content-Length while sending a large file: the
# reviewer measured 6 MB spooled before the eventual per-field size check caught it. The cap is now also
# enforced on the raw request stream itself (`_bounded_stream` below), independent of Content-Length.
VOICE_CONTENT_LENGTH_OVERHEAD = 65_536


async def _bounded_stream(stream, cap: int):
    """Wraps an ASGI body stream, raising MultiPartException once more than `cap` bytes have been read in
    total -- bounds memory/spool usage during parsing itself, regardless of what Content-Length claims."""
    total = 0
    async for chunk in stream:
        total += len(chunk)
        if total > cap:
            raise MultiPartException(f"body exceeded {cap} bytes")
        yield chunk


async def _parse_bounded_form(request: Request, cap: int) -> FormData:
    """A hand-rolled `request.form()` that bounds the raw stream (see `_bounded_stream`) instead of relying
    on `max_part_size`, which Starlette does not apply to file parts."""
    content_type, _ = parse_options_header(request.headers.get("content-type", ""))
    stream = _bounded_stream(request.stream(), cap)
    if content_type == b"multipart/form-data":
        return await MultiPartParser(request.headers, stream).parse()
    if content_type == b"application/x-www-form-urlencoded":
        return await FormParser(request.headers, stream).parse()
    async for _ in stream:  # drain so the ASGI server doesn't see an unread body
        pass
    return FormData()


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
        # the engine cites quotes without boxes; add pdfplumber's, as phase 3 and the precomputed chips do (issue #14)
        res = res.model_copy(update={"findings": with_citation_boxes(res.findings, deps.inputs().tender_pdf)})
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
        # Fix round 1/2, Important #1: FastAPI/Starlette parse the whole multipart body before a route's own
        # File(...)/Form(...) dependencies run, with no cap by default -- on Cloud Run the temp filesystem is
        # RAM, so an unbounded upload is a real resource risk. A browser always sends Content-Length for a
        # FormData body, so a missing one (e.g. a chunked upload) is rejected outright, before touching the
        # body at all. A declared size over budget is rejected the same way. A lying small Content-Length is
        # still caught, because _parse_bounded_form bounds the raw stream itself as it parses (see above).
        declared = request.headers.get("content-length")
        if declared is None:
            return err(411, "length_required")
        try:
            if int(declared) > VOICE_MAX_BYTES + VOICE_CONTENT_LENGTH_OVERHEAD:
                return err(413, "audio_too_large")
        except ValueError:
            return err(411, "length_required")  # an unparsable Content-Length is as good as missing
        try:
            form = await _parse_bounded_form(request, VOICE_MAX_BYTES + VOICE_CONTENT_LENGTH_OVERHEAD)
        except MultiPartException:
            return err(413, "audio_too_large")
        audio = form.get("audio")
        if audio is None or not hasattr(audio, "read"):
            return err(422, "audio_required")
        data = await audio.read(VOICE_MAX_BYTES + 1)
        if len(data) > VOICE_MAX_BYTES:
            return err(413, "audio_too_large")
        revision_ref = form.get("revision_ref") or "seed:hall-a@r2"
        if not isinstance(revision_ref, str):
            return err(422, "bad_revision_ref")  # e.g. sent as a file part instead of a text field
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
