"""Co-pilot (spec §6.4, §6.5): revision loading, finding explanations, push-to-talk voice (Task 16)."""
import functools
import json
import logging
import math
import re
import threading
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from kirchhoff.contracts import DesignModel, Finding, ProjectBundle
from kirchhoff.engine.whatif import PARAM_BOUNDS
from kirchhoff.runs.revisions import load_revision_model

from .runner import Attachment, run_json
from .specs import COPILOT, COPILOT_VOICE
from .trust import allowed_ids_for, fill_finding, fmt_number, sanitize

try:
    from kirchhoff.enterprise.client import EnterpriseUnavailable  # WS4-owned module
except ImportError:
    class EnterpriseUnavailable(Exception):
        """Placeholder when kirchhoff.enterprise.client is unavailable (never actually raised)."""

log = logging.getLogger("kirchhoff.copilot")
# Fix round 1 (Important #3): separate pools for engine work (what-if) and LLM work (explain). Explain's
# underlying runner call can retry internally (with_retries, 429/5xx) and run long; sharing one pool let a
# burst of slow/retried explain calls starve every what-if request behind its own timeout. Each pool's
# futures are explicitly cancelled on timeout so a queued-but-not-yet-started task never blocks a worker.
_ENGINE_POOL = ThreadPoolExecutor(max_workers=8)
_LLM_POOL = ThreadPoolExecutor(max_workers=8)
SEED_REF = re.compile(r"^seed:([a-z0-9-]+)@([A-Za-z0-9_-]+)$")
WS_REF = re.compile(r"^ws:([A-Za-z0-9_-]+)$")


class RevisionNotFound(KeyError):
    """The revision (or its seed bundle) does not exist."""


class BadRevisionRef(ValueError):
    """`revision_ref` matches neither the `ws:` nor `seed:` pattern (distinct from any other ValueError --
    e.g. a corrupt seed bundle's pydantic ValidationError -- so only this one maps to 422 bad_revision_ref)."""


def call_with_timeout(fn: Callable[[], Any], timeout_s: float, pool: ThreadPoolExecutor = _ENGINE_POOL) -> Any:
    fut = pool.submit(fn)
    try:
        return fut.result(timeout=timeout_s)
    except FuturesTimeoutError:
        fut.cancel()
        raise


@functools.lru_cache(maxsize=16)
def _bundle(path: str, mtime: float) -> ProjectBundle:
    return ProjectBundle.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_seed_bundle(seed_dir: Path, project_id: str) -> ProjectBundle:
    p = Path(seed_dir) / f"{project_id}.json"
    if not p.exists():
        raise RevisionNotFound(project_id)
    return _bundle(str(p), p.stat().st_mtime)


def _model_blob_missing(deps, uid: str, doc: dict) -> bool:
    """True only when the revision defers to a model blob (R7) and that blob is actually absent -- an inline
    `model` (seed bundles, or a ws revision that still carries one) never needs this check."""
    if doc.get("model") or not doc.get("model_url"):
        return False
    return not deps.blobs.exists(f"workspaces/{uid}/{doc['model_url']}")


def load_revision(deps, uid: str, ref: str) -> tuple[DesignModel, list[Finding]]:
    if m := WS_REF.match(ref):
        rev = m.group(1)
        doc = deps.store.get_doc(f"workspaces/{uid}/revisions/{rev}")
        if doc is None or _model_blob_missing(deps, uid, doc):
            raise RevisionNotFound(ref)
        findings = [Finding.model_validate(d)
                    for d in deps.store.list_docs(f"workspaces/{uid}/revisions/{rev}/findings")]
        return load_revision_model(deps, uid, doc), findings
    if m := SEED_REF.match(ref):
        bundle = load_seed_bundle(deps.seed_dir, m.group(1))
        r = next((r for r in bundle.revisions if r.id == m.group(2)), None)
        if r is None or r.model is None:
            raise RevisionNotFound(ref)
        return r.model, list(bundle.findings.get(r.id, []))
    raise BadRevisionRef(f"bad revision_ref {ref!r}")


def explain_text(deps, model: DesignModel, finding: Finding, *, deadline: float | None = None) -> str:
    """`deadline` (a `time.monotonic()` value) is passed by voice (`answer_voice`), so the explanation is
    bounded by the voice request's one deadline. That case runs the LLM call on a plain thread rather than
    through `_LLM_POOL` (Fix round 1, Minor: voice's tools used to run on an `_LLM_POOL` worker, where a
    nested submit to the same fixed-size pool could deadlock it)."""
    template = finding.explanation or f"{finding.title}: {{value}} against a limit of {{limit}}."
    clauses = ", ".join(c.clause for c in finding.tender_refs if c.clause) or "none"
    standards = ", ".join(f"{c.standard} {c.clause or ''}".strip() for c in finding.clause_refs) or "none"
    msg = (f"Finding {finding.id}: {finding.title}. Rule {finding.rule_id} on element {finding.element_id}; "
           f"status {finding.status}. Formula: {finding.formula or 'n/a'}. Inputs: {json.dumps(finding.inputs)}. "
           f"Tender clauses: {clauses}. Standards: {standards}. "
           "Explain why in two sentences. Write {value} and {limit} instead of any number.")
    if deadline is None:
        # A single LLM attempt, submitted to the dedicated LLM pool (never the engine pool what-if uses) so
        # a burst of explain calls can never delay a what-if request. `deps.erp()` runs on this thread while
        # the LLM call runs in the background, so the two overlap instead of adding to the /api latency
        # budget. Task 15 residual fix (a): one deadline, taken right after submit, covers both the
        # (possibly slow) deps.erp() call below and the wait -- not COPILOT.timeout_s + 1 *in addition to*
        # whatever deps.erp() already spent, which could push the total past the ~10s-per-/api budget.
        fut = _LLM_POOL.submit(deps.runner.run, COPILOT, f"explain:{finding.id}", msg)
        deadline = time.monotonic() + COPILOT.timeout_s + 1

        def wait(t: float):
            return fut.result(timeout=t)

        cancel = fut.cancel
    else:
        box: list = []
        error: list = []

        def call() -> None:
            # Fix round 2, Minor: a thread target's uncaught exception does not propagate to whoever joins
            # it, so `box` would stay empty and `wait()` below would raise an unrelated IndexError instead
            # of the real cause -- caught here and re-raised from `wait()` once the thread is joined.
            try:
                box.append(deps.runner.run(COPILOT, f"explain:{finding.id}", msg))
            except Exception as exc:
                error.append(exc)

        thread = threading.Thread(target=call, daemon=True)
        thread.start()

        def wait(t: float):
            thread.join(t)
            if thread.is_alive():
                raise FuturesTimeoutError()
            if error:
                raise error[0]
            return box[0]

        cancel = lambda: None  # noqa: E731 -- the thread is a daemon; it is simply abandoned on timeout
    try:
        extra_ids = [finding.element_id, *deps.erp().ids()]
        res = wait(max(0.0, deadline - time.monotonic()))
        # The one surface that fills placeholders (fill_finding below, from this finding's engine record).
        text = sanitize(res.text, allowed_ids_for(model, extra=extra_ids), template, placeholders=True)
    except Exception as exc:
        cancel()
        log.warning("explain fallback for %s: %r", finding.id, exc)
        text = template
    return fill_finding(text, finding.value, finding.limit, finding.unit)


# --- Task 16: /api/voice push-to-talk fallback (same three tools as WS3's Live TOOL_DECLARATIONS) ---
# Issue #36: one model round trip. Automatic function calling cost two sequential model turns (pick and call
# the tool, then write the reply), 7-8 s steady and 26 s with a retry, against a 9 s budget. Now the model
# returns only {transcript, tool, args}; the server validates the tool and its args with the checks the
# tools applied, runs the tool itself, and the answer is the code-authored engine_summary (R13/R14).

WHAT_IF_PARAMS = ("rack_kw", "liquid_fraction", "dv_limit_pct", "tx_loading_cap_pct")
# The tools voice may ask the server to run, with their argument names: exactly WS3's Live TOOL_DECLARATIONS
# (tests/api/test_api_voice.py checks the parity).
VOICE_TOOLS: dict[str, tuple[str, ...]] = {"what_if": ("param", "value"),
                                           "explain_finding": ("finding_id", "element_id"),
                                           "focus_element": ("element_id",)}
# A safety net over the one round trip. COPILOT_VOICE.timeout_s (the model call's own HTTP timeout) sits just
# under it and the call is a single attempt, so a hung call frees its worker by the time the 504 goes out.
VOICE_TIMEOUT_S = 20.0
VOICE_PROMPT = ("The attached audio is the engineer's question about the current design revision. "
                "Reply with the JSON object only.")
NO_MATCH = "I could not match that to a design question; try a what-if chip."
OUT_OF_RANGE = "That what-if value is outside what the engine can check; try a what-if chip."
# sanitize's template for a transcript sentence that carries a number the engine never ran with.
TRANSCRIPT_ELIDED = "\u2026"


class VoiceIntent(BaseModel):
    """The one model reply. Deliberately loose: the server validates `tool` and `args` itself, so an unknown
    tool or a bad argument still keeps the transcript and gets an honest answer instead of a parse failure."""
    transcript: str | None = None
    tool: str | None = None
    args: dict[str, Any] | None = None


def engine_summary(results: list[dict]) -> str:
    parts = []
    for r in results:
        if r["name"] == "what_if":
            fails = sorted({f["rule_id"] for f in r["result"]["findings"] if f["status"] == "fail"})
            head = f"With {r['args']['param']} at {fmt_number(r['args']['value'])}, "
            parts.append(head + (f"these checks fail: {', '.join(fails)}." if fails else "every check still passes."))
        elif r["name"] == "explain_finding":
            parts.append(r["result"]["text"])
        elif r["name"] == "focus_element":
            parts.append(f"Showing {r['args']['element_id']}.")
    return " ".join(parts) or NO_MATCH


def _id_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _id_resolver(ids: Iterable[str]) -> Callable[[Any], str | None]:
    """Maps a model-written id to the real id it names: an exact match, else the one real id it spells when
    case, hyphens and spaces are ignored ("hz2" or "H Z2" -> "H-Z2"; ambiguous spellings match nothing).
    Anything else -> None, so only a real id is ever echoed."""
    real = set(ids)
    by_key: dict[str, str | None] = {}
    for i in real:
        k = _id_key(i)
        by_key[k] = None if k in by_key else i

    def resolve(raw: Any) -> str | None:
        if not isinstance(raw, str):
            return None
        if raw in real:
            return raw
        k = _id_key(raw)
        return by_key.get(k) if k else None

    return resolve


def _finite_number(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        return None
    try:
        x = float(v)
    except (ValueError, OverflowError):
        return None
    return x if math.isfinite(x) else None


def _is_timeout(exc: BaseException) -> bool:
    """A timeout inside the model call: the builtin TimeoutError (AdkRunner's asyncio.wait_for), the HTTP
    client's own (httpx.ReadTimeout and its siblings, raised when GenaiRunner's per-call timeout fires just
    before VOICE_TIMEOUT_S) or a Vertex 504 (DEADLINE_EXCEEDED)."""
    return (isinstance(exc, TimeoutError) or "Timeout" in type(exc).__name__
            or getattr(exc, "code", None) == 504)


def answer_voice(deps, uid: str, ref: str, audio: bytes, mime: str) -> dict:
    # One deadline, taken before load_revision, bounds the model call and the tool run together (Fix round 2,
    # Minor). deps.scenario() and deps.erp() are fetched lazily, only when what_if runs (their only use): a
    # focus_element-only call has no business waiting on another request's slow ERP refresh.
    deadline = time.monotonic() + VOICE_TIMEOUT_S
    model, findings = load_revision(deps, uid, ref)
    by_id = {f.id: f for f in findings}
    erp_box: list = []
    scn_box: list = []
    verified: list[str] = []  # model-written tokens checked against the engine's records or bounds

    def remaining() -> float:
        return max(0.0, deadline - time.monotonic())

    def erp():
        if not erp_box:
            erp_box.append(deps.erp())
        return erp_box[0]

    def scn():
        if not scn_box:
            scn_box.append(deps.scenario())
        return scn_box[0]

    def real(ids: Iterable[str], raw: Any) -> str | None:
        """The real id that `raw` (model-written) names, or None; its spelling becomes a verified token."""
        rid = _id_resolver(ids)(raw)
        if rid:
            verified.append(raw)
        return rid

    def ask() -> VoiceIntent:
        # One runner call: no tools (so no automatic function calling) and no JSON repair turn.
        intent, _ = run_json(deps.voice_runner, COPILOT_VOICE, "voice", VOICE_PROMPT, VoiceIntent,
                             attachments=[Attachment(audio, mime)], repair=False)
        return intent

    try:
        # The model call runs on the LLM pool (the split Task 15 made for explain), never the engine pool
        # /api/what-if uses.
        intent = call_with_timeout(ask, remaining(), pool=_LLM_POOL)
    except TimeoutError:
        raise
    except ValidationError:  # Fix round 2, Minor: a server bug, never masked as a "could not match" fallback
        raise
    except Exception as exc:
        if _is_timeout(exc):
            raise FuturesTimeoutError() from exc
        log.warning("voice fallback: %r", exc)  # model or JSON failure: no tool, the honest fallback answer
        intent = VoiceIntent()

    args = intent.args or {}
    results: list[dict] = []
    answer = NO_MATCH
    try:
        if intent.tool == "what_if" and args.get("param") in WHAT_IF_PARAMS:
            param, value = args["param"], _finite_number(args.get("value"))
            lo, hi = PARAM_BOUNDS[param]
            if value is None or not lo <= value <= hi:
                answer = OUT_OF_RANGE  # the same up-front check /api/what-if makes (ruling P2-R17)
            else:
                verified.append(fmt_number(value))
                # Engine work runs on the engine pool, as /api/what-if's does, under the remaining deadline.
                r = call_with_timeout(lambda: deps.engine.what_if(scn(), model, param, value, ref, erp()),
                                      remaining(), pool=_ENGINE_POOL)
                results.append({"name": "what_if", "args": {"param": param, "value": value},
                                "result": r.model_dump(mode="json")})
        elif intent.tool == "explain_finding":
            # A real finding id, else the element's failing finding (or its first), as the tool did.
            f = by_id.get(real(by_id, args.get("finding_id")) or "")
            if f is None and (el := real({x.element_id for x in findings}, args.get("element_id"))):
                on_el = [x for x in findings if x.element_id == el]
                f = next((x for x in on_el if x.status == "fail"), on_el[0] if on_el else None)
            if f is not None:
                # The existing explain path, bounded by its own budget and by what is left of this request's.
                text = explain_text(deps, model, f, deadline=min(deadline, time.monotonic() + COPILOT.timeout_s + 1))
                results.append({"name": "explain_finding", "args": {"finding_id": f.id}, "result": {"text": text}})
        elif intent.tool == "focus_element":
            # Fix round 1, Critical: only an id that actually exists on the model is trusted, so an invented
            # one carrying its own narration ("the 7.77 percent feeder") never reaches the answer.
            if el := real(allowed_ids_for(model), args.get("element_id")):
                results.append({"name": "focus_element", "args": {"element_id": el}, "result": {"focused": el}})
    except TimeoutError:
        raise
    except EnterpriseUnavailable:  # Fix round 1, Important #3: the route maps this to 503, not a fallback
        raise
    except ValidationError:  # Fix round 2, Minor: a server bug (e.g. a malformed engine or ERP record)
        raise
    except Exception as exc:  # e.g. an ERP-side ValueError (a sandbox 422): no tool result, the honest fallback
        log.warning("voice tool fallback: %r", exc)
        results = []
    if results:
        answer = engine_summary(results)
    # The transcript is the user's words but model-written, so it goes through sanitize with placeholders off:
    # it may show real ids and the values the server validated, never a number the engine did not run with.
    erp_ids = erp_box[0].ids() if erp_box else ()
    transcript = (intent.transcript or "").strip()
    if transcript:
        transcript = sanitize(transcript, allowed_ids_for(model, extra=[*erp_ids, *by_id, *verified]),
                              TRANSCRIPT_ELIDED, placeholders=False)
    return {"transcript": transcript, "answer": answer, "tool_results": results}
