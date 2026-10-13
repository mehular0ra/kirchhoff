import logging
import os
import threading
from typing import Callable

from fastapi import Header, HTTPException

logger = logging.getLogger("kirchhoff")

_firebase_app_lock = threading.Lock()


def _ensure_firebase_app() -> None:
    import firebase_admin

    if not firebase_admin._apps:
        with _firebase_app_lock:
            if not firebase_admin._apps:
                firebase_admin.initialize_app(options={"projectId": "ordinal-mep"})


def firebase_verify(token: str) -> str:
    from firebase_admin import auth

    _ensure_firebase_app()
    return auth.verify_id_token(token)["uid"]


def appcheck_verify(token: str) -> None:
    from firebase_admin import app_check

    _ensure_firebase_app()
    app_check.verify_token(token)


def make_current_uid(verify_token: Callable[[str], str]):
    def current_uid(authorization: str | None = Header(default=None),
                    x_firebase_appcheck: str | None = Header(default=None)) -> str:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        try:
            uid = verify_token(authorization.removeprefix("Bearer "))
        except Exception as exc:  # invalid/expired token
            logger.warning("auth failed: %s", type(exc).__name__)
            raise HTTPException(status_code=401, detail="invalid token") from exc
        if os.environ.get("KIRCHHOFF_REQUIRE_APPCHECK") == "1":
            if not x_firebase_appcheck:
                raise HTTPException(status_code=401, detail="missing app check token")
            try:
                appcheck_verify(x_firebase_appcheck)
            except Exception as exc:
                logger.warning("auth failed: %s", type(exc).__name__)
                raise HTTPException(status_code=401, detail="invalid app check token") from exc
        return uid
    return current_uid
