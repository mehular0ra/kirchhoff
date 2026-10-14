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
TOPOLOGY_ORDER = ("2N", "DR", "BLOCK")


def topology_words(s: str) -> set[str]:
    """Every topology id literally present in `s`, generically (ruling P2-R13): App. B's "Block or
    distributed redundancy acceptable" contains two topology words, BLOCK and DR, and both must be
    detected without hard-coding that clause's text. Covers the topology words the ruling names by
    example ("block", "distributed", "N+1", "2N", "DR") without hard-coding any particular clause."""
    t = s.casefold()
    found: set[str] = set()
    if re.search(r"\b2n\b", t):
        found.add("2N")
    if re.search(r"\bn\+1\b", t):
        found.add("N+1")
    if "distributed" in t or re.search(r"\bdr\b", t):
        found.add("DR")
    if "block" in t:
        found.add("BLOCK")
    return found


def canonical_topology(s: str) -> str | None:
    words = topology_words(s)
    for t in TOPOLOGY_ORDER:
        if t in words:
            return t
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


def _topology_backstop(reqs: list[Requirement], doc_id: str) -> OpenQuestion | None:
    """Ruling P2-R13: the model often invents contradictions (fabricated quotes, rejected by
    verification) or simply misses the real one. Deterministic fallback, generic and not tied to any
    particular clause id: if a verified main-body requirement's value canonicalizes to one topology X,
    and a verified appendix requirement's quote literally contains a *different* topology word, the
    conflict is real and both requirements are already verified -- build the same OpenQuestion shape
    `_question` would, with `default_resolution` the main-body value."""
    for main in reqs:
        if not (main.verified and _is_main(main.citation.clause)) or main.value is None:
            continue
        x = canonical_topology(str(main.value))
        if x is None:
            continue
        for alt in reqs:
            if not (alt.verified and not _is_main(alt.citation.clause)):
                continue
            others = sorted(topology_words(alt.text) - {x})
            if not others:
                continue
            text = f"{main.citation.clause} requires {x} but {alt.citation.clause} allows {' or '.join(others)}."
            return OpenQuestion(
                id="Q-redundancy", text=text, options=[x, "compare_all"], default_resolution=x,
                citations=[Citation(doc_id=doc_id, page=main.citation.page, quote=main.citation.quote,
                                    bbox=main.citation.bbox, clause=main.citation.clause),
                          Citation(doc_id=doc_id, page=alt.citation.page, quote=alt.citation.quote,
                                   bbox=alt.citation.bbox, clause=alt.citation.clause)])
    return None


def build_brief(project_id: str, doc_id: str, extraction: TenderExtraction, verify: Verify,
                drawing_check: dict, allowed: set[str],
                on_backstop: Callable[[OpenQuestion], None] | None = None) -> DesignBrief:
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
    if not any(canonical_topology(q.default_resolution) for q in questions):
        backstop = _topology_backstop(reqs, doc_id)
        if backstop is not None:
            questions.append(backstop)
            if on_backstop is not None:
                on_backstop(backstop)
    return DesignBrief(project_id=project_id, requirements=reqs, open_questions=questions,
                       drawing_check=drawing_check)
