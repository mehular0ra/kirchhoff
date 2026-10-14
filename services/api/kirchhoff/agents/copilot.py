"""Co-pilot (spec §6.4, §6.5): revision loading, finding explanations, push-to-talk voice (Task 16)."""
import functools
import json
import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from kirchhoff.contracts import DesignModel, Finding, ProjectBundle
from kirchhoff.runs.revisions import load_revision_model

from .runner import Attachment, run_json
from .specs import COPILOT, COPILOT_VOICE
from .trust import allowed_ids_for, fill_finding, fmt_number, sanitize

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


def explain_text(deps, model: DesignModel, finding: Finding) -> str:
    template = finding.explanation or f"{finding.title}: {{value}} against a limit of {{limit}}."
    clauses = ", ".join(c.clause for c in finding.tender_refs if c.clause) or "none"
    standards = ", ".join(f"{c.standard} {c.clause or ''}".strip() for c in finding.clause_refs) or "none"
    msg = (f"Finding {finding.id}: {finding.title}. Rule {finding.rule_id} on element {finding.element_id}; "
           f"status {finding.status}. Formula: {finding.formula or 'n/a'}. Inputs: {json.dumps(finding.inputs)}. "
           f"Tender clauses: {clauses}. Standards: {standards}. "
           "Explain why in two sentences. Write {value} and {limit} instead of any number.")
    # A single LLM attempt, submitted to the dedicated LLM pool (never the engine pool what-if uses) so a
    # burst of explain calls can never delay a what-if request. `deps.erp()` runs on this thread while the
    # LLM call runs in the background, so the two overlap instead of adding to the /api latency budget.
    fut = _LLM_POOL.submit(deps.runner.run, COPILOT, f"explain:{finding.id}", msg)
    try:
        extra_ids = [finding.element_id, *deps.erp().ids()]
        res = fut.result(timeout=COPILOT.timeout_s + 1)
        text = sanitize(res.text, allowed_ids_for(model, extra=extra_ids), template)
    except Exception as exc:
        fut.cancel()
        log.warning("explain fallback for %s: %r", finding.id, exc)
        text = template
    return fill_finding(text, finding.value, finding.limit, finding.unit)


# --- Task 16: /api/voice push-to-talk fallback (same three tools as WS3's Live TOOL_DECLARATIONS) ---

WHAT_IF_PARAMS = ("rack_kw", "liquid_fraction", "dv_limit_pct", "tx_loading_cap_pct")
VOICE_TIMEOUT_S = 9.0
VOICE_PROMPT = ("The attached audio is the engineer's question about the current design revision. Use the tools "
                'to answer, then reply with JSON {"transcript": the words you heard, "answer": one or two sentences}.')
NO_MATCH = "I could not match that to a design question; try a what-if chip."


class VoiceReply(BaseModel):
    transcript: str = ""
    answer: str = ""


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


def answer_voice(deps, uid: str, ref: str, audio: bytes, mime: str) -> dict:
    model, findings = load_revision(deps, uid, ref)
    scn, erp, by_id = deps.scenario(), deps.erp(), {f.id: f for f in findings}
    results: list[dict] = []

    def what_if(param: str, value: float) -> dict:
        """Re-check the current design with one input changed (loads change, equipment stays frozen).
        param is one of rack_kw, liquid_fraction, dv_limit_pct, tx_loading_cap_pct."""
        if param not in WHAT_IF_PARAMS:
            return {"error": f"param must be one of {', '.join(WHAT_IF_PARAMS)}"}
        # Engine work runs on the engine pool (same pool /api/what-if uses via call_with_timeout's default),
        # kept separate from the LLM pool the surrounding voice call runs on below, so neither starves the
        # other under load.
        r = _ENGINE_POOL.submit(deps.engine.what_if, scn, model, param, float(value), ref, erp).result()
        results.append({"name": "what_if", "args": {"param": param, "value": float(value)},
                        "result": r.model_dump(mode="json")})
        return {"failing_rules": sorted({f.rule_id for f in r.findings if f.status == "fail"}),
                "impact_chain": r.impact_chain[:6]}

    def explain_finding(finding_id: str = "", element_id: str = "") -> dict:
        """Explain one checker finding, given its id such as R05:FA-01, or the element id such as FA-01."""
        f = by_id.get(finding_id)
        if f is None and element_id:
            on_el = [x for x in findings if x.element_id == element_id]
            f = next((x for x in on_el if x.status == "fail"), on_el[0] if on_el else None)
        if f is None:
            return {"error": "unknown finding"}
        text = explain_text(deps, model, f)
        results.append({"name": "explain_finding", "args": {"finding_id": f.id}, "result": {"text": text}})
        return {"text": text}

    def focus_element(element_id: str) -> dict:
        """Show an element such as FA-01, H-Z2 or CDU-4 on the canvas."""
        results.append({"name": "focus_element", "args": {"element_id": element_id},
                        "result": {"focused": element_id}})
        return {"focused": element_id}

    def ask() -> VoiceReply:
        reply, _ = run_json(deps.voice_runner, COPILOT_VOICE, "voice", VOICE_PROMPT, VoiceReply,
                            tools=[what_if, explain_finding, focus_element], attachments=[Attachment(audio, mime)])
        return reply

    try:
        # The voice round trip is dominated by the model call (automatic function calling runs the tools
        # above inline), so it is submitted to the LLM pool -- the same split Task 15 made for explain --
        # rather than the engine pool /api/what-if's call_with_timeout defaults to.
        reply = call_with_timeout(ask, VOICE_TIMEOUT_S, pool=_LLM_POOL)
    except TimeoutError:
        raise
    except Exception as exc:  # model or JSON failure: answer from what the engine produced
        log.warning("voice fallback: %r", exc)
        reply = VoiceReply()
    answer = sanitize(reply.answer, allowed_ids_for(model, extra=[*erp.ids(), *by_id]), engine_summary(results))
    return {"transcript": reply.transcript, "answer": answer, "tool_results": results}
