import os
from typing import Callable

from fastapi import Depends, FastAPI

from kirchhoff.store import Store

from .auth import firebase_verify, make_current_uid
from .hello import make_router as hello_router

VERSION = os.environ.get("K_REVISION", "dev")


def create_app(store: Store | None = None, verify_token: Callable[[str], str] | None = None) -> FastAPI:
    if store is None:
        from kirchhoff.store.firestore import FirestoreStore
        store = FirestoreStore()
    current_uid = make_current_uid(verify_token or firebase_verify)
    app = FastAPI(title="Kirchhoff API")

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "version": VERSION}

    @app.get("/api/whoami")
    def whoami(uid: str = Depends(current_uid)) -> dict:
        return {"uid": uid}

    app.include_router(hello_router(store, current_uid))
    app.state.store = store
    app.state.current_uid = current_uid
    return app
