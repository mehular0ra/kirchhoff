from kirchhoff.contracts import Citation, DesignBrief, OpenQuestion, Requirement
from kirchhoff.intake.score import load_ground_truth, score_intake, value_matches
from kirchhoff.intake.verify import PdfText, value_in_quote, verify_quote


def test_verified_quote_has_bbox(tender_pdf):
    with PdfText(tender_pdf) as pdf:
        chk = verify_quote(pdf, 4, "shall not exceed 2.0% at the worst-case design current", 2.0)
    assert chk.ok and chk.reason == "ok"
    x0, top, x1, bottom = chk.bbox
    assert x0 < x1 and top < bottom


def test_quote_spanning_a_line_break_verifies(tender_pdf, tender):
    with PdfText(tender_pdf) as pdf:
        assert verify_quote(pdf, 2, tender.clause("§2.3").text, 26).ok


def test_wrong_page_wrong_value_and_out_of_range(tender_pdf):
    q = "shall not exceed 2.0% at the worst-case design current"
    with PdfText(tender_pdf) as pdf:
        assert verify_quote(pdf, 3, q, 2.0).reason == "quote_not_found"
        assert verify_quote(pdf, 4, q, 2.5).reason == "value_not_in_quote"
        assert verify_quote(pdf, 99, q, 2.0).reason == "page_out_of_range"
        assert verify_quote(pdf, 4, "2.0%", 2.0).reason == "quote_too_short"


def test_wrong_unit_is_unverified_and_correct_unit_verifies(tender_pdf):
    q = "shall not exceed 2.0% at the worst-case design current"
    with PdfText(tender_pdf) as pdf:
        assert verify_quote(pdf, 4, q, 2.0, "A").reason == "unit_not_in_quote"
        assert verify_quote(pdf, 4, q, 2.0, "%").ok
        assert verify_quote(pdf, 4, q, 2.0).ok  # unit optional, defaults to no check


def test_quote_with_unicode_hyphen_verifies(tender_pdf):
    # §4.5 renders "single-failure"; an extracted quote with U+2010 should still normalize and match.
    with PdfText(tender_pdf) as pdf:
        assert verify_quote(pdf, 4, "worst single‐failure load", None).ok


def test_value_in_quote_handles_words_strings_and_separators():
    assert value_in_quote(2, "supplied from two independent UPS-backed power systems")
    assert value_in_quote("2N", "The critical power system shall be 2N from the transformers")
    assert value_in_quote(1546, "failover current of 1,546 A")
    assert value_in_quote("2.0", "shall not exceed 2.0% at")
    assert value_in_quote(None, "anything at all")
    assert not value_in_quote(3, "two independent systems")


def test_ground_truth_is_consistent_with_the_fixture_tender(tender, ground_truth_path):
    gt = load_ground_truth(ground_truth_path)
    for c in tender.clauses:
        assert gt.clause_pages[c.id] == c.page
    for r in gt.requirements:
        assert value_in_quote(r.value, tender.clause(r.clause).text), (r.clause, r.value)


def test_value_matches():
    assert value_matches(2.0, "2") and value_matches("2N", "2n") and value_matches(None, 5)
    assert not value_matches(80, 100) and not value_matches("N+1", "2N")


def _req(rid, clause, page, value, verified=True):
    return Requirement(id=rid, text="q", value=value, unit=None, verified=verified,
                       citation=Citation(doc_id="tender-hall-a", page=page, quote="q", clause=clause))


def test_score_intake(ground_truth_path):
    gt = load_ground_truth(ground_truth_path)
    brief = DesignBrief(project_id="hall-b", requirements=[
        _req("REQ-a", "§2.3", 2, 26), _req("REQ-b", "§4.6", 4, 2.0), _req("REQ-c", "§4.2", 4, "2N"),
        _req("REQ-d", "§4.3", 3, 70), _req("REQ-e", "§6.4", 6, None, verified=False)],
        open_questions=[OpenQuestion(id="Q-redundancy", text="t", options=["2N", "compare_all"],
                                     default_resolution="2N", citations=[
                                         Citation(doc_id="d", page=4, quote="q", clause="§4.2"),
                                         Citation(doc_id="d", page=7, quote="q", clause="App. B")])])
    s = score_intake(brief, gt)
    assert s["extracted"] == 5 and s["verified"] == 4
    assert s["recall"] == 3 / 32 and s["precision"] == 3 / 4
    assert s["citation_resolution"] == 3 / 4  # REQ-d cites page 3 for a page-4 clause
    assert s["contradictions_found"] == 1 and s["contradictions_expected"] == 1
