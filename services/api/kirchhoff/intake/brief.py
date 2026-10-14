import re
from collections.abc import Callable
from typing import Any

from kirchhoff.agents.trust import sanitize
from kirchhoff.contracts import Citation, DesignBrief, OpenQuestion, Requirement

from .extract import ExtractedContradiction, TenderExtraction
from .textnorm import normalize
from .verify import QuoteCheck

UNVERIFIED_TEMPLATE = "Requirement not accepted: the quote was not found on the cited page."
Verify = Callable[[int, str, Any, str | None], QuoteCheck]


def canonical_topology(s: str) -> str | None:
    t = s.casefold()
    if re.search(r"\b2n\b", t):
        return "2N"
    if "distributed" in t or t.strip() == "dr":
        return "DR"
    if "block" in t:
        return "BLOCK"
    return None


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "conflict"


def _is_main(clause: str) -> bool:
    return not clause.startswith("App.")


def _question(c: ExtractedContradiction, doc_id: str, verify: Verify, allowed: set[str]) -> OpenQuestion | None:
    ca, cb = verify(c.page_a, c.quote_a, None, None), verify(c.page_b, c.quote_b, None, None)
    if not (ca.ok and cb.ok):
        return None
    # clause_a wins both when it is the main body and when neither side is (nothing to prefer over it).
    main_value = c.value_a if _is_main(c.clause_a) or not _is_main(c.clause_b) else c.value_b
    default = canonical_topology(main_value) or main_value
    text = sanitize(c.summary, allowed, f"{c.clause_a} and {c.clause_b} disagree; the main body governs by default.")
    return OpenQuestion(
        id=f"Q-{_slug(c.topic)}", text=text, options=[default, "compare_all"], default_resolution=default,
        citations=[Citation(doc_id=doc_id, page=c.page_a, quote=normalize(c.quote_a), bbox=ca.bbox, clause=c.clause_a),
                   Citation(doc_id=doc_id, page=c.page_b, quote=normalize(c.quote_b), bbox=cb.bbox, clause=c.clause_b)])


def build_brief(project_id: str, doc_id: str, extraction: TenderExtraction, verify: Verify,
                drawing_check: dict, allowed: set[str]) -> DesignBrief:
    reqs: list[Requirement] = []
    seen: dict[str, int] = {}
    for r in extraction.requirements:
        seen[r.key] = seen.get(r.key, 0) + 1
        rid = f"REQ-{r.key}" if seen[r.key] == 1 else f"REQ-{r.key}-{seen[r.key]}"
        chk = verify(r.page, r.verbatim_quote, r.value, r.unit)
        if chk.ok:
            quote = normalize(r.verbatim_quote)
            reqs.append(Requirement(id=rid, text=quote, value=r.value, unit=r.unit, verified=True,
                                    citation=Citation(doc_id=doc_id, page=r.page, quote=quote, bbox=chk.bbox,
                                                      clause=r.clause)))
        else:
            # R12: unverified text is ALWAYS the fixed template. The LLM's quote is untrusted prose and
            # must never reach the UI even when it happens to contain no disallowed digits (sanitize()
            # only swaps in a template for text that fails the digit allowlist, which is not the same
            # guarantee).
            reqs.append(Requirement(id=rid, text=UNVERIFIED_TEMPLATE, value=None, unit=r.unit, verified=False,
                                    citation=Citation(doc_id=doc_id, page=r.page, quote="", clause=r.clause)))
    questions = [q for c in extraction.contradictions if (q := _question(c, doc_id, verify, allowed)) is not None]
    return DesignBrief(project_id=project_id, requirements=reqs, open_questions=questions,
                       drawing_check=drawing_check)
