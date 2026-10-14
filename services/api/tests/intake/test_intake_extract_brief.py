from kirchhoff.agents.runner import ReplayRunner
from kirchhoff.intake.brief import UNVERIFIED_TEMPLATE, build_brief, canonical_topology
from kirchhoff.intake.extract import ExtractedContradiction, TenderExtraction, extract_tender, read_drawing
from kirchhoff.intake.verify import PdfText, verify_quote
from kirchhoff.runs.fakes import FAKE_REPLIES

AGREES = {"agrees": True, "differences": []}


def _brief(tender_pdf, extraction):
    with PdfText(tender_pdf) as pdf:
        return build_brief("hall-b", "tender-hall-a", extraction, lambda p, q, v: verify_quote(pdf, p, q, v),
                           AGREES, set())


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
