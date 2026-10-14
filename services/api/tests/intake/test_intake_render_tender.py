from pathlib import Path

import pdfplumber
import pytest
from pydantic import ValidationError

from kirchhoff.intake.render import render_tender_pdf
from kirchhoff.intake.tender_schema import TenderClause, load_tender
from kirchhoff.intake.textnorm import PDF_TEXT_KW, normalize

FIX = Path(__file__).parent / "fixtures"
REPO_TENDER = Path(__file__).resolve().parents[4] / "scenarios" / "hall_a" / "tender.yaml"


def test_fixture_has_contradiction_and_lead_time_limit():
    t = load_tender(FIX / "tender.yaml")
    assert "2N" in t.clause("§4.2").text and t.clause("§4.2").section == "main"
    assert t.clause("App. B").section == "appendix"
    assert t.limit("max_lead_time_weeks") == 26 and t.limit("dv_max_pct") == 2.0


def test_non_latin1_text_is_rejected():
    with pytest.raises(ValidationError):
        TenderClause(id="§9.9", title="x", page=1, text="ΔV ≤ 2%", quote="2%")


def test_quote_must_be_verbatim_in_text():
    with pytest.raises(ValidationError):
        TenderClause(id="§9.9", title="x", page=1, text="shall not exceed 2.0%", quote="shall not exceed 2.5%")


def test_bad_clause_id_is_rejected():
    with pytest.raises(ValidationError):
        TenderClause(id="4.6", title="x", page=1, text="shall not exceed 2.0%", quote="2.0%")


def test_each_clause_and_quote_render_on_the_declared_page(tmp_path: Path):
    tender = load_tender(FIX / "tender.yaml")
    pdf = render_tender_pdf(tender, tmp_path / "tender.pdf")
    with pdfplumber.open(pdf) as doc:
        assert len(doc.pages) == max(c.page for c in tender.clauses)
        for c in tender.clauses:
            text = normalize(doc.pages[c.page - 1].extract_text(**PDF_TEXT_KW) or "")
            assert c.id in text, c.id
            assert normalize(c.text) in text and normalize(c.quote) in text, c.id


def test_render_is_deterministic(tmp_path: Path):
    tender = load_tender(FIX / "tender.yaml")
    a = render_tender_pdf(tender, tmp_path / "a.pdf").read_bytes()
    b = render_tender_pdf(tender, tmp_path / "b.pdf").read_bytes()
    assert a == b


@pytest.mark.skipif(not REPO_TENDER.exists(), reason="WS1 has not written scenarios/hall_a/tender.yaml yet")
def test_repo_tender_matches_fixture():
    def key(t):
        return [t.doc_id] + [(c.id, c.page, normalize(c.text), c.quote, c.limits) for c in t.clauses]
    assert key(load_tender(REPO_TENDER)) == key(load_tender(FIX / "tender.yaml"))
