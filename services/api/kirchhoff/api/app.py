import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import Depends, FastAPI

from kirchhoff.runs.deps import Deps
from kirchhoff.store import Store

from . import copilot_routes, files_routes, runs_routes, workspace_routes
from .auth import firebase_verify, make_current_uid

VERSION = os.environ.get("K_REVISION", "dev")
log = logging.getLogger("kirchhoff")


def _warm_up_engine(deps: Deps) -> None:
    try:
        deps.engine.warm_up()
    except Exception:
        log.exception("engine warm_up failed")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Pays the engine's first-call cost (pandapower import, JIT/setup) once, in the background, so it
    # never blocks startup or the health check and never runs at import time. Under KIRCHHOFF_FAKES=1
    # the fake engine's warm_up() is already a cheap no-op, so there is no need to special-case it.
    threading.Thread(target=_warm_up_engine, args=(app.state.deps,), daemon=True).start()
    yield


def create_app(store: Store | None = None, verify_token: Callable[[str], str] | None = None,
               deps: Deps | None = None) -> FastAPI:
    if deps is None:
        from .deps import build_production_deps
        deps = build_production_deps(store)
    store = deps.store
    current_uid = make_current_uid(verify_token or firebase_verify)
    app = FastAPI(title="Kirchhoff API", lifespan=_lifespan)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "version": VERSION}

    @app.get("/api/whoami")
    def whoami(uid: str = Depends(current_uid)) -> dict:  # permanent (P0 fix wave); smoke test probes it
        return {"uid": uid}

    app.include_router(workspace_routes.make_router(deps, current_uid))
    app.include_router(runs_routes.make_router(deps, current_uid))
    app.include_router(copilot_routes.make_router(deps, current_uid))
    app.include_router(files_routes.make_router(deps, current_uid))
    try:
        from .enterprise_proxy import make_router as enterprise_router  # WS4-owned module
    except ImportError:
        enterprise_router = None
    if enterprise_router is not None:
        # Flattened directly into app.routes (rather than app.include_router, which wraps the sub-router
        # in a lazily-resolved _IncludedRouter in this FastAPI version): WS4's test_p2_create_app_mounts_
        # the_proxy inspects app.routes for these paths directly, and dispatch works identically either way
        # since enterprise_proxy's router adds no prefix, dependencies or sub-lifespan of its own.
        app.routes.extend(enterprise_router(store, current_uid).routes)
    app.state.store, app.state.current_uid, app.state.deps = store, current_uid, deps
    return app
