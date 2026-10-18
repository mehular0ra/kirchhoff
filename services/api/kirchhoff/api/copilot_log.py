"""An opt-in record of the co-pilot's API calls, for debugging a conversation afterwards.

With KIRCHHOFF_LOG_DIR set, every /api/what-if, /api/explain and /api/voice call appends one JSON line to
<dir>/copilot.jsonl: when, which route, a short hash of the caller (never the uid or the token), the status, how long it
took, and what was asked and answered. Unset (the deployed default), nothing is written and the routes run as before.
Recording never changes a response or raises: a failed write is logged and dropped.
"""
import functools
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable

_log = logging.getLogger("kirchhoff.copilot.audit")
_warn = logging.getLogger("kirchhoff")
_handler: RotatingFileHandler | None = None

Fields = Callable[[dict, int, Any], dict]


def configure() -> None:
    """Starts recording if KIRCHHOFF_LOG_DIR names a folder. A second call changes nothing."""
    global _handler
    folder = os.environ.get("KIRCHHOFF_LOG_DIR")
    if not folder or _handler is not None:
        return
    Path(folder).mkdir(parents=True, exist_ok=True)
    _handler = RotatingFileHandler(Path(folder) / "copilot.jsonl", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _log.addHandler(_handler)
    _log.setLevel(logging.INFO)
    _log.propagate = False  # these lines belong in the file, not mixed into the server's own log


def reset() -> None:
    """Stops recording (tests, and a changed KIRCHHOFF_LOG_DIR)."""
    global _handler
    if _handler is not None:
        _log.removeHandler(_handler)
        _handler.close()
        _handler = None


def _write(route: str, kwargs: dict, started: float, status: int, body: Any, fields: Fields) -> None:
    try:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "route": route,
            "user": hashlib.sha256(str(kwargs.get("uid")).encode()).hexdigest()[:8],
            "status": status,
            "ms": round((time.monotonic() - started) * 1000),
            **fields(kwargs, status, body),
        }
        _log.info(json.dumps(entry, default=str, ensure_ascii=False))
    except Exception:  # recording must never change what the visitor gets
        _warn.exception("co-pilot audit record failed")


def _status_and_body(result: Any) -> tuple[int, Any]:
    """A route returns its JSON body (200) or a JSONResponse carrying a status and {"detail": ...}."""
    if hasattr(result, "status_code"):
        try:
            return result.status_code, json.loads(result.body)
        except (TypeError, ValueError):
            return result.status_code, {}
    return 200, result


def audited(route: str, fields: Fields):
    """Records a sync route handler's call; `fields(kwargs, status, body)` says what to keep of the request and answer."""

    def decorate(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            if _handler is None:
                return fn(*args, **kwargs)
            started = time.monotonic()
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                _write(route, kwargs, started, 500, {"detail": repr(exc)}, fields)
                raise
            status, body = _status_and_body(result)
            _write(route, kwargs, started, status, body, fields)
            return result

        return inner

    return decorate


def audited_async(route: str, fields: Fields):
    """The same for an async route handler."""

    def decorate(fn):
        @functools.wraps(fn)
        async def inner(*args, **kwargs):
            if _handler is None:
                return await fn(*args, **kwargs)
            started = time.monotonic()
            try:
                result = await fn(*args, **kwargs)
            except Exception as exc:
                _write(route, kwargs, started, 500, {"detail": repr(exc)}, fields)
                raise
            status, body = _status_and_body(result)
            _write(route, kwargs, started, status, body, fields)
            return result

        return inner

    return decorate


# What to keep, per route. Only the request's own fields and the engine's answer: never the uid, the token or the audio.

def what_if_fields(kwargs: dict, status: int, body: Any) -> dict:
    ask = kwargs["body"]
    out: dict = {"revision_ref": ask.revision_ref, "param": ask.param, "value": ask.value}
    if status == 200:
        findings = body["findings"]
        out |= {"n_findings": len(findings), "failing": sorted({f["rule_id"] for f in findings if f["status"] == "fail"}),
                "impact_chains": len(body["impact_chain"])}
    else:
        out["error"] = body.get("detail")
    return out


def explain_fields(kwargs: dict, status: int, body: Any) -> dict:
    ask = kwargs["body"]
    out: dict = {"revision_ref": ask.revision_ref, "finding_id": ask.finding_id}
    out |= {"text": body["text"]} if status == 200 else {"error": body.get("detail")}
    return out


def voice_fields(kwargs: dict, status: int, body: Any) -> dict:
    out: dict = {"audio_bytes": int(kwargs["request"].headers.get("content-length") or 0)}
    if status == 200:
        out |= {"transcript": body["transcript"], "tools": [t["name"] for t in body["tool_results"]], "answer": body["answer"]}
    else:
        out["error"] = body.get("detail")
    return out
