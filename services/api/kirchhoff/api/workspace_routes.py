from fastapi import APIRouter, Depends

from kirchhoff.runs.deps import Deps
from kirchhoff.runs.leases import lease_is_live

from .errors import err


def make_router(deps: Deps, current_uid) -> APIRouter:
    router = APIRouter()

    @router.post("/api/workspace")
    def ensure_workspace(uid: str = Depends(current_uid)):
        path = f"workspaces/{uid}"
        created = deps.store.get_doc(path) is None
        if created:
            deps.store.set_doc(path, {"created_at": deps.clock(), "last_run_at": None, "run_starts": []})
        return {"uid": uid, "created": created}

    @router.post("/api/workspace/reset")
    def reset_workspace(uid: str = Depends(current_uid)):
        now = deps.clock()
        if any(lease_is_live(r.get("lease"), now) for r in deps.store.list_docs(f"workspaces/{uid}/runs")):
            return err(409, "run_in_progress")
        deps.store.delete_tree(f"workspaces/{uid}")
        deps.blobs.delete_prefix(f"workspaces/{uid}/")
        deps.enterprise.reset_visitor(uid)
        return {"ok": True}

    return router
