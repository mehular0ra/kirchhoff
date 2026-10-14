from kirchhoff.agents.runner import ReplayRunner
from kirchhoff.intake.brief import UNVERIFIED_TEMPLATE, build_brief, canonical_topology
from kirchhoff.intake.extract import ExtractedContradiction, TenderExtraction, extract_tender, read_drawing
from kirchhoff.intake.verify import PdfText, verify_quote
from kirchhoff.runs.fakes import FAKE_REPLIES

AGREES = {"agrees": True, "differences": []}


def _brief(tender_pdf, extraction):
    with PdfText(tender_pdf) as pdf:
        return build_brief("hall-b", "tender-hall-a", extraction,
                           lambda p, q, v, u=None: verify_quote(pdf, p, q, v, u), AGREES, set())


def test_extract_and_build_brief(tender_pdf):
    extraction, res = extract_tender(ReplayRunner(FAKE_REPLIES), tender_pdf.read_bytes())
    assert res.tokens_in == 9000
    brief = _brief(tender_pdf, extraction)
    assert len(brief.requirements) == 8 and sum(r.verified for r in brief.requirements) == 7
    bad = next(r for r in brief.requirements if not r.verified)
    assert bad.id == "REQ-ups_autonomy_min" and bad.value is None and bad.text == UNVERIFIED_TEMPLATE
    dv = next(r for r in brief.requirements if r.id == "REQ-dv_max_pct")
    assert dv.value == 2.0 and dv.citation.page == 4 and dv.citation.clause == "§4.6" and dv.citation.bbox
    assert dv.text == "shall not exceed 2.0% at the worst-case design current"
    (q,) = brief.open_questions
    assert q.id == "Q-redundancy" and q.default_resolution == "2N" and q.options == ["2N", "compare_all"]
    assert [c.clause for c in q.citations] == ["§4.2", "App. B"] and all(c.bbox for c in q.citations)
    assert q.text == "§4.2 requires 2N but App. B accepts block or distributed redundancy."
    assert q.resolution is None and brief.drawing_check == AGREES


def test_read_drawing_returns_structured_read():
    read, _ = read_drawing(ReplayRunner(FAKE_REPLIES), b"%PDF-1.4")
    assert read.grid_x == ["1", "2", "3", "4", "5", "6"] and read.overall_mm == [60000, 36000]


def test_contradiction_with_unverifiable_quote_is_dropped(tender_pdf):
    c = ExtractedContradiction(topic="redundancy", clause_a="§4.2", page_a=4, quote_a="The system shall be 3N",
                               value_a="3N", clause_b="App. B", page_b=7,
                               quote_b="Block or distributed redundancy acceptable", value_b="DR",
                               summary="x")
    assert _brief(tender_pdf, TenderExtraction(requirements=[], contradictions=[c])).open_questions == []


def test_appendix_listed_first_still_defaults_to_main_body(tender_pdf):
    c = ExtractedContradiction(topic="Power redundancy", clause_a="App. B", page_a=7,
                               quote_a="Block or distributed redundancy acceptable", value_a="BLOCK",
                               clause_b="§4.2", page_b=4, quote_b="The critical power distribution shall be 2N",
                               value_b="2N redundancy", summary="They disagree in 2 places.")
    (q,) = _brief(tender_pdf, TenderExtraction(requirements=[], contradictions=[c])).open_questions
    assert q.id == "Q-power-redundancy" and q.default_resolution == "2N"
    assert q.text == "App. B and §4.2 disagree; the main body governs by default."


def test_duplicate_keys_get_suffixes(tender_pdf):
    ex = TenderExtraction.model_validate({"requirements": [
        {"key": "tx_loading", "clause": "§4.3", "page": 4, "value": 80, "unit": "%",
         "verbatim_quote": "Transformer loading shall not exceed 80% of rating in normal operation"},
        {"key": "tx_loading", "clause": "§4.3", "page": 4, "value": 100, "unit": "%",
         "verbatim_quote": "100% of rating under any single failure"}]})
    assert [r.id for r in _brief(tender_pdf, ex).requirements] == ["REQ-tx_loading", "REQ-tx_loading-2"]


def test_canonical_topology():
    assert canonical_topology("2N redundancy") == "2N"
    assert canonical_topology("distributed redundant") == "DR"
    assert canonical_topology("Block redundant") == "BLOCK"
    assert canonical_topology("N+1") is None


def test_unverified_digit_free_quote_still_gets_the_template(tender_pdf):
    ex = TenderExtraction.model_validate({"requirements": [
        {"key": "x", "clause": "§9.9", "page": 4, "value": None, "unit": None,
         "verbatim_quote": "This sentence is not present on this page at all."}]})
    (r,) = _brief(tender_pdf, ex).requirements
    assert not r.verified and r.value is None and r.text == UNVERIFIED_TEMPLATE


def test_unverified_quote_with_only_allowlisted_tokens_still_gets_the_template(tender_pdf):
    # §4.2's real text on the wrong page: no digits outside allowed tokens (2N, §4.2), so a naive
    # sanitize() pass-through would leave the raw LLM text in place. It must still be the template.
    ex = TenderExtraction.model_validate({"requirements": [
        {"key": "redundancy", "clause": "§4.2", "page": 7, "value": "2N", "unit": None,
         "verbatim_quote": "The critical power distribution shall be 2N, with each rack fed from two "
                           "independent systems."}]})
    (r,) = _brief(tender_pdf, ex).requirements
    assert not r.verified and r.value is None and r.text == UNVERIFIED_TEMPLATE


def test_unverified_quote_with_digits_still_gets_the_template(tender_pdf):
    ex = TenderExtraction.model_validate({"requirements": [
        {"key": "y", "clause": "§9.9", "page": 4, "value": 99, "unit": None,
         "verbatim_quote": "This made-up sentence claims 99 units that are not on this page."}]})
    (r,) = _brief(tender_pdf, ex).requirements
    assert not r.verified and r.value is None and r.text == UNVERIFIED_TEMPLATE


def test_wrong_unit_requirement_is_unverified(tender_pdf):
    ex = TenderExtraction.model_validate({"requirements": [
        {"key": "dv_max_pct", "clause": "§4.6", "page": 4, "value": 2.0, "unit": "A",
         "verbatim_quote": "shall not exceed 2.0% at the worst-case design current"}]})
    (r,) = _brief(tender_pdf, ex).requirements
    assert not r.verified and r.value is None and r.text == UNVERIFIED_TEMPLATE


def test_correct_unit_requirement_verifies(tender_pdf):
    ex = TenderExtraction.model_validate({"requirements": [
        {"key": "dv_max_pct", "clause": "§4.6", "page": 4, "value": 2.0, "unit": "%",
         "verbatim_quote": "shall not exceed 2.0% at the worst-case design current"}]})
    (r,) = _brief(tender_pdf, ex).requirements
    assert r.verified and r.value == 2.0


def _redundancy_reqs():
    return TenderExtraction.model_validate({"requirements": [
        {"key": "redundancy", "clause": "§4.2", "page": 4, "value": "2N", "unit": None,
         "verbatim_quote": "The critical power distribution shall be 2N, with each rack fed from two "
                           "independent systems."},
        {"key": "redundancy_alt", "clause": "App. B", "page": 7, "value": "BLOCK", "unit": None,
         "verbatim_quote": "Block or distributed redundancy acceptable, subject to the loading limits of "
                           "§4.3."}]})


def test_backstop_derives_the_redundancy_question_when_the_model_found_no_contradiction(tender_pdf):
    # Ruling P2-R13: the model's contradictions list is EMPTY, but the verified §4.2 and App. B
    # requirements disagree on topology, so the deterministic backstop must derive Q-redundancy.
    brief = _brief(tender_pdf, _redundancy_reqs())
    assert sum(r.verified for r in brief.requirements) == 2
    (q,) = brief.open_questions
    assert q.id == "Q-redundancy" and q.default_resolution == "2N"
    assert [c.clause for c in q.citations] == ["§4.2", "App. B"]
    assert all(c.bbox for c in q.citations)


def test_backstop_does_not_duplicate_the_models_own_verified_contradiction(tender_pdf):
    ex = _redundancy_reqs()
    ex.contradictions.append(ExtractedContradiction(
        topic="redundancy", clause_a="§4.2", page_a=4, quote_a="The critical power distribution shall be 2N",
        value_a="2N", clause_b="App. B", page_b=7,
        quote_b="Block or distributed redundancy acceptable", value_b="BLOCK",
        summary="§4.2 requires 2N but App. B accepts block or distributed redundancy."))
    brief = _brief(tender_pdf, ex)
    assert len(brief.open_questions) == 1
    assert brief.open_questions[0].id == "Q-redundancy"


def test_backstop_ignores_fabricated_contradictions_and_requirements(tender_pdf):
    # The live diagnostics' fabricated examples: quotes that are not on the cited page at all.
    ex = TenderExtraction.model_validate({"requirements": [
        {"key": "lead_time_alt", "clause": "§1.3", "page": 1, "value": 20, "unit": "weeks",
         "verbatim_quote": "Alternative equipment may be delivered within 20 weeks."},
        {"key": "redundancy_alt", "clause": "§5.4", "page": 5, "value": "N+1", "unit": None,
         "verbatim_quote": "An N+1 arrangement is also acceptable."}],
        "contradictions": [{"topic": "clearance", "clause_a": "§5.1", "page_a": 5,
                            "quote_a": "clear height shall be 3.5 m", "value_a": "3.5",
                            "clause_b": "App. B", "page_b": 7, "quote_b": "clear height shall be 3.0 m",
                            "value_b": "3.0", "summary": "x"}]})
    brief = _brief(tender_pdf, ex)
    assert all(not r.verified for r in brief.requirements)
    assert brief.open_questions == []


def test_neither_clause_main_body_defaults_to_clause_a(tender_pdf):
    # Both sides cite an appendix: clause_a wins (no main body present to prefer).
    c = ExtractedContradiction(topic="redundancy", clause_a="App. A", page_a=7,
                               quote_a="Block or distributed redundancy acceptable", value_a="BLOCK",
                               clause_b="App. B", page_b=7,
                               quote_b="Block or distributed redundancy acceptable", value_b="DR",
                               summary="Two appendices disagree.")
    (q,) = _brief(tender_pdf, TenderExtraction(requirements=[], contradictions=[c])).open_questions
    assert q.default_resolution == "BLOCK"
