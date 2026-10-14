"""Co-pilot (spec §6.4, §6.5): revision loading, finding explanations, push-to-talk voice (Task 16)."""
import functools
import json
import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from kirchhoff.contracts import DesignModel, Finding, ProjectBundle
from kirchhoff.runs.revisions import load_revision_model

from .specs import COPILOT
from .trust import allowed_ids_for, fill_finding, sanitize

log = logging.getLogger("kirchhoff.copilot")
_POOL = ThreadPoolExecutor(max_workers=8)
SEED_REF = re.compile(r"^seed:([a-z0-9-]+)@([A-Za-z0-9_-]+)$")
WS_REF = re.compile(r"^ws:([A-Za-z0-9_-]+)$")


class RevisionNotFound(KeyError):
    """The revision (or its seed bundle) does not exist."""


def call_with_timeout(fn: Callable[[], Any], timeout_s: float) -> Any:
    return _POOL.submit(fn).result(timeout=timeout_s)


@functools.lru_cache(maxsize=16)
def _bundle(path: str, mtime: float) -> ProjectBundle:
    return ProjectBundle.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_seed_bundle(seed_dir: Path, project_id: str) -> ProjectBundle:
    p = Path(seed_dir) / f"{project_id}.json"
    if not p.exists():
        raise RevisionNotFound(project_id)
    return _bundle(str(p), p.stat().st_mtime)


def load_revision(deps, uid: str, ref: str) -> tuple[DesignModel, list[Finding]]:
    if m := WS_REF.match(ref):
        rev = m.group(1)
        doc = deps.store.get_doc(f"workspaces/{uid}/revisions/{rev}")
        if doc is None:
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
    raise ValueError(f"bad revision_ref {ref!r}")


def explain_text(deps, model: DesignModel, finding: Finding) -> str:
    template = finding.explanation or f"{finding.title}: {{value}} against a limit of {{limit}}."
    clauses = ", ".join(c.clause for c in finding.tender_refs if c.clause) or "none"
    standards = ", ".join(f"{c.standard} {c.clause or ''}".strip() for c in finding.clause_refs) or "none"
    msg = (f"Finding {finding.id}: {finding.title}. Rule {finding.rule_id} on element {finding.element_id}; "
           f"status {finding.status}. Formula: {finding.formula or 'n/a'}. Inputs: {json.dumps(finding.inputs)}. "
           f"Tender clauses: {clauses}. Standards: {standards}. "
           "Explain why in two sentences. Write {value} and {limit} instead of any number.")
    try:
        res = call_with_timeout(lambda: deps.runner.run(COPILOT, f"explain:{finding.id}", msg), COPILOT.timeout_s + 1)
        text = sanitize(res.text, allowed_ids_for(model, extra=[finding.element_id, *deps.erp().ids()]), template)
    except Exception as exc:
        log.warning("explain fallback for %s: %r", finding.id, exc)
        text = template
    return fill_finding(text, finding.value, finding.limit, finding.unit)
