import mimetypes
import re

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse, Response

from kirchhoff.runs.deps import Deps

from .errors import err

FILE_RE = re.compile(r"^(exports|revisions)/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
SIGNED_URL_TTL_S = 600


def make_router(deps: Deps, current_uid) -> APIRouter:
    router = APIRouter()

    @router.get("/api/files/{path:path}")
    def files(path: str, redirect: bool = True, uid: str = Depends(current_uid)):
        if not FILE_RE.match(path) or ".." in path:
            return err(404, "not_found")
        full = f"workspaces/{uid}/{path}"
        if not deps.blobs.exists(full):
            return err(404, "not_found")
        try:
            url = deps.blobs.signed_url(full, SIGNED_URL_TTL_S)
        except NotImplementedError:  # local in-process blobs: serve the bytes
            media = mimetypes.guess_type(path)[0] or "application/octet-stream"
            return Response(deps.blobs.get(full), media_type=media, headers={"X-Kirchhoff-Inline": "1"})
        if not redirect:  # web client: fetch the signed URL without auth headers (no CORS preflight)
            return {"url": url, "expires_in": SIGNED_URL_TTL_S}
        return RedirectResponse(url, status_code=302)

    return router
