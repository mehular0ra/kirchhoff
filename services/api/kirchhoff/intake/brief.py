import re
from collections.abc import Callable, Iterable, Iterator
from typing import Any, Literal

from kirchhoff.agents.trust import sanitize
from kirchhoff.contracts import Citation, DesignBrief, OpenQuestion, Requirement

from .extract import ExtractedContradiction, TenderExtraction
from .textnorm import normalize, normalize_clause
from .verify import QuoteCheck, value_in_quote

UNVERIFIED_TEMPLATE = "Requirement not accepted: the quote was not found on the cited page."
QUESTION_TEMPLATE = "These tender clauses disagree; the main body governs by default."  # no number words (§6.3)
Verify = Callable[[int, str, Any, str | None], QuoteCheck]
ClausePrinted = Callable[[int, str], bool]  # (page, normalised label) -> the tender prints it there
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
    """Question ids from letters only (P2 final fix wave, Important 2): the topic is model free text, and a
    topic such as "lead time 26" must not put a model-written number into an id."""
    return re.sub(r"[^a-z]+", "-", s.lower()).strip("-") or "conflict"


def _key_slug(key: str) -> str:
    """Requirement ids are printed in the calc report's Id column: letters and underscores only."""
    return re.sub(r"_+", "_", re.sub(r"[^a-z_]+", "_", key.casefold())).strip("_")


def _clause(label: str | None, page: int, printed: ClausePrinted) -> str | None:
    """The clause id to show: the model's label normalised (`§4.2`, `App. B`) AND printed on the cited page.
    Anything else is None, so the chip falls back to "Tender · p.N". The page check is what keeps a normalised
    forgery ("Section 12345" -> "§12345", which the digit allowlist would pass) off every surface."""
    clause = normalize_clause(label)
    return clause if clause is not None and printed(page, clause) else None


def _clause_kind(clause: str | None) -> Literal["main", "appendix"] | None:
    """A requirement with no clause label is neither main body nor appendix: it can never drive the
    backstop, and in `_question` it never outranks a labelled main-body clause. Labels reaching this are
    already normalised by `_clause`, so every appendix reads "App. X"."""
    if clause is None or not clause.strip():
        return None
    return "appendix" if clause.strip().startswith("App.") else "main"


def _question_text(text: str, clause_a: str | None, clause_b: str | None, allowed: Iterable[str]) -> str:
    """The one sanitize path for every OpenQuestion.text (spec §6.3), model-reported or backstop.
    Clause labels are LLM free text that verify_quote never checks (it checks only the quote and the
    value), so the clause-naming fallback is itself sanitized down to the fixed, digit-free
    QUESTION_TEMPLATE: a forged label such as "Clause 12345" can never reach the UI or the orchestrator."""
    fallback = (sanitize(f"{clause_a} and {clause_b} disagree; the main body governs by default.", allowed,
                         QUESTION_TEMPLATE, placeholders=False) if clause_a and clause_b else QUESTION_TEMPLATE)
    return sanitize(text, allowed, fallback, placeholders=False)


_SIDE_RANK = {"main": 0, None: 1, "appendix": 2}


def _verified_default(value: str | None, quote: str) -> str | None:
    """The plan-gate default (and its option label) from the VERIFIED quote, never the model's free text: the
    topology the quote names (the model's pick among several it names, else the canonical first); for any
    other conflict, the model's value only when the quote literally contains it. None drops the question."""
    words, picked = topology_words(quote), canonical_topology(value or "")
    if picked in words:
        return picked
    if topology := canonical_topology(quote):
        return topology
    value = normalize(value)
    return value if value and value_in_quote(value, quote) else None


def _question(c: ExtractedContradiction, doc_id: str, verify: Verify, allowed: set[str],
              printed: ClausePrinted) -> OpenQuestion | None:
    ca, cb = verify(c.page_a, c.quote_a, None, None), verify(c.page_b, c.quote_b, None, None)
    if not (ca.ok and cb.ok):
        return None
    clause_a, clause_b = _clause(c.clause_a, c.page_a, printed), _clause(c.clause_b, c.page_b, printed)
    # The main body governs: a main-body side first, then an unlabelled one, an appendix last; side a on a tie.
    sides = [(clause_a, c.value_a, normalize(c.quote_a)), (clause_b, c.value_b, normalize(c.quote_b))]
    _, main_value, main_quote = min(sides, key=lambda side: _SIDE_RANK[_clause_kind(side[0])])
    default = _verified_default(main_value, main_quote)
    if default is None:
        return None  # nothing verified to default to; the topology backstop still covers redundancy
    text = _question_text(c.summary, clause_a, clause_b, allowed)
    return OpenQuestion(
        id=f"Q-{_slug(c.topic)}", text=text, options=[default, "compare_all"], default_resolution=default,
        citations=[Citation(doc_id=doc_id, page=c.page_a, quote=normalize(c.quote_a), bbox=ca.bbox, clause=clause_a),
                   Citation(doc_id=doc_id, page=c.page_b, quote=normalize(c.quote_b), bbox=cb.bbox, clause=clause_b)])


def _key_words(rid: str) -> set[str]:
    """The extractor's snake_case key, recovered from the id `build_brief` assigns ("REQ-<key>", or
    "REQ-<key>-<n>" for a repeated key; a key with no letters gives the bare "REQ"), split into its words.
    `Requirement` has no other key field. Keys are letters and underscores only, so the "-<n>" suffix is
    always build_brief's own."""
    if not rid.startswith("REQ-"):
        return set()
    key = re.sub(r"-\d+$", "", rid.removeprefix("REQ-"))
    return {w for w in re.split(r"[^a-z0-9]+", key.casefold()) if w}


def _key_affinity(main: Requirement, alt: Requirement) -> tuple[bool, int]:
    """Identical keys first, then the number of key words the two share; (False, 0) is no key match."""
    a, b = _key_words(main.id), _key_words(alt.id)
    return bool(a) and a == b, len(a & b)


def _topology_pairs(reqs: list[Requirement]) -> Iterator[tuple[Requirement, Requirement, str, list[str]]]:
    """Every (main, appendix, X, other topologies) conflict among the VERIFIED requirements, in order."""
    for main in reqs:
        if not (main.verified and _clause_kind(main.citation.clause) == "main") or main.value is None:
            continue
        x = canonical_topology(str(main.value))
        if x is None:
            continue
        for alt in reqs:
            if not (alt.verified and _clause_kind(alt.citation.clause) == "appendix"):
                continue
            if others := sorted(topology_words(alt.text) - {x}):
                yield main, alt, x, others


def _topology_backstop(reqs: list[Requirement], doc_id: str, allowed: Iterable[str] = ()) -> OpenQuestion | None:
    """Ruling P2-R13: the model often invents contradictions (fabricated quotes, rejected by
    verification) or simply misses the real one. Deterministic fallback, generic and not tied to any
    particular clause id: if a verified main-body requirement's value canonicalizes to one topology X,
    and a verified appendix requirement's quote literally contains a *different* topology word, the
    conflict is real and both requirements are already verified -- build the same OpenQuestion shape
    `_question` would, with `default_resolution` the main-body value. Among several such pairs the one
    whose requirement keys match best wins; with no key match at all, the first pair (`max` keeps the
    first of equal maxima)."""
    pairs = list(_topology_pairs(reqs))
    if not pairs:
        return None
    main, alt, x, others = max(pairs, key=lambda p: _key_affinity(p[0], p[1]))
    m, a = main.citation, alt.citation
    text = _question_text(f"{m.clause} requires {x} but {a.clause} allows {' or '.join(others)}.",
                          m.clause, a.clause, allowed)
    return OpenQuestion(
        id="Q-redundancy", text=text, options=[x, "compare_all"], default_resolution=x,
        citations=[Citation(doc_id=doc_id, page=m.page, quote=m.quote, bbox=m.bbox, clause=m.clause),
                   Citation(doc_id=doc_id, page=a.page, quote=a.quote, bbox=a.bbox, clause=a.clause)])


def _clause_id(clause: str | None) -> str:
    return "".join((clause or "").split()).casefold()


def _cites_both(q: OpenQuestion, pair: OpenQuestion) -> bool:
    """True when `q` already cites BOTH clauses `pair` cites (any order, spacing or case)."""
    return {_clause_id(c.clause) for c in pair.citations} <= {_clause_id(c.clause) for c in q.citations}


def _unique_id(q: OpenQuestion, taken: set[str]) -> OpenQuestion:
    """The plan gate keys questions by id, so a clash would silently drop one: suffix like requirement ids."""
    qid, n = q.id, 1
    while qid in taken:
        n += 1
        qid = f"{q.id}-{n}"
    return q if qid == q.id else q.model_copy(update={"id": qid})


def build_brief(project_id: str, doc_id: str, extraction: TenderExtraction, verify: Verify,
                drawing_check: dict, allowed: set[str],
                on_backstop: Callable[[OpenQuestion], None] | None = None, *,
                clause_printed: ClausePrinted) -> DesignBrief:
    """`clause_printed(page, label)` (production: verify.clause_on_page) says whether the tender prints a
    normalised clause label on that page; a label it rejects is dropped (None)."""
    reqs: list[Requirement] = []
    seen: dict[str, int] = {}
    for r in extraction.requirements:
        base = f"REQ-{key}" if (key := _key_slug(r.key)) else "REQ"
        seen[base] = seen.get(base, 0) + 1
        rid = base if seen[base] == 1 else f"{base}-{seen[base]}"
        chk = verify(r.page, r.verbatim_quote, r.value, r.unit)
        clause = _clause(r.clause, r.page, clause_printed)
        if chk.ok:
            quote = normalize(r.verbatim_quote)
            reqs.append(Requirement(id=rid, text=quote, value=r.value, unit=r.unit, verified=True,
                                    citation=Citation(doc_id=doc_id, page=r.page, quote=quote, bbox=chk.bbox,
                                                      clause=clause)))
        else:
            # R12: unverified text is ALWAYS the fixed template. The LLM's quote is untrusted prose and
            # must never reach the UI even when it happens to contain no disallowed digits (sanitize()
            # only swaps in a template for text that fails the digit allowlist, which is not the same
            # guarantee).
            # The unit is model free text too (it is printed in the calc report), so it goes with the value.
            reqs.append(Requirement(id=rid, text=UNVERIFIED_TEMPLATE, value=None, unit=None, verified=False,
                                    citation=Citation(doc_id=doc_id, page=r.page, quote="", clause=clause)))
    questions: list[OpenQuestion] = []
    for c in extraction.contradictions:
        if (q := _question(c, doc_id, verify, allowed, clause_printed)) is not None:
            # The plan gate keys answers by id, so two model questions on one topic must not share one.
            questions.append(_unique_id(q, {x.id for x in questions}))
    backstop = _topology_backstop(reqs, doc_id, allowed)
    # Suppressed ONLY by a verified question that already cites both clauses of this very pair.
    if backstop is not None and not any(_cites_both(q, backstop) for q in questions):
        backstop = _unique_id(backstop, {q.id for q in questions})
        questions.append(backstop)
        if on_backstop is not None:
            on_backstop(backstop)
    return DesignBrief(project_id=project_id, requirements=reqs, open_questions=questions,
                       drawing_check=drawing_check)
