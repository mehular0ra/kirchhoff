import io
import re

import pdfplumber

from kirchhoff.agents.docs_export import SECTIONS, BlobExporter, boq_csv, calc_report_pdf, latin1
from kirchhoff.contracts import (Citation, DesignBrief, Finding, LedgerEntry, PRLine, Requirement, Revision,
                                 TopologyOption)
from kirchhoff.runs.blobs import MemoryBlobStore

LINES = [PRLine(material_id="TX-3150", description="Transformer 3.15 MVA", qty=6, unit_price=118000.0,
                lead_time_weeks=12),
         PRLine(material_id="BW-1600", description="Busway 1,600 A", qty=410, unit_price=420.0, lead_time_weeks=8)]
FIX = Finding(id="R05:FA-01", rule_id="R05", element_id="FA-01", status="fail", title="Voltage drop", value=2.16,
              limit=2.0, unit="%", formula="ΔU% = 100·√3·I·L·(R cosφ + X sinφ)/U",
              fix={"candidate": "FA-01:cable-CBL-240-8P", "label": "Parallel cable feeder for FA-01", "agent": "power",
                   "reason": "Largest voltage-drop margin per dollar."},
              rejected_fix={"candidate": "FA-01:upsize-BW-2000", "label": "Upsize FA-01 to 2,000 A busway"})
REV = Revision(id="abc-r2", project_id="hall-b", parent="abc-r1", author="Kirchhoff agents", hash="f" * 64,
               check_summary={"pass": 40, "fail": 0, "warn": 0, "n/a": 2}, status="checked",
               ledger=[LedgerEntry(kind="not_checked", agent="checker", text="Selectivity")], created_at=0.0)
BRIEF = DesignBrief(project_id="hall-b", requirements=[Requirement(
    id="REQ-dv_max_pct", text="shall not exceed 2.0%", value=2.0, unit="%", verified=True,
    citation=Citation(doc_id="tender-hall-a", page=4, quote="shall not exceed 2.0%", clause="§4.6"))])
OPTS = [TopologyOption(id="2N", installed_mva=18.9, normal_loading_pct=38, failover_loading_pct=76, cost=4.1e6,
                       losses_kw=310, max_lead_time_weeks=16, spof_count=0)]


def _pdf_text(data: bytes) -> str:
    with pdfplumber.open(io.BytesIO(data)) as doc:
        return " ".join(p.extract_text(x_tolerance=1.5) or "" for p in doc.pages)


def test_latin1_maps_engineering_symbols():
    assert latin1("ΔU ≤ √3 · I") == "dU <= sqrt3 · I"


def test_latin1_handles_r08_r10_cooling_formulas():
    # Real engine formula strings (kirchhoff/engine/findings.py, R08-R10), which exercise symbols the
    # original map missed: the minus sign "−" (U+2212, distinct from a hyphen), rho "ρ", pi "π" and a
    # combining dot above "̇" (as in "V̇").
    r08 = "Σ Q_CDU − spare units ≥ Σ P_rack·f_liquid per zone"
    r09 = "q_rack ≥ max(q_OEM,min, Q/(ρ·c_p·ΔT))"
    r10 = "v = 4·V̇/(π·D²) ≤ v_max"
    for formula in (r08, r09, r10):
        out = latin1(formula)
        assert "?" not in out  # no latin-1 replacement-character fallback
    assert latin1(r08) == "sum Q_CDU - spare units >= sum P_rack·f_liquid per zone"
    assert "rho" in latin1(r09) and "dT" in latin1(r09)
    assert "pi" in latin1(r10) and "V_dot" in latin1(r10)


def test_latin1_maps_curly_quotes_and_ellipsis():
    assert latin1("‘quoted’ “text” … done") == "'quoted' \"text\" ... done"


def test_boq_csv_has_header_lines_and_total():
    rows = boq_csv(LINES).decode().strip().split("\n")
    assert rows[0] == "material_id,description,qty,unit_price_usd,line_total_usd,lead_time_weeks"
    assert rows[1] == "TX-3150,Transformer 3.15 MVA,6,118000.00,708000.00,12"
    assert rows[-1] == "TOTAL,,416,,880200.00,12"


def test_calc_report_contains_every_section_in_order():
    data = calc_report_pdf(rev=REV, findings=[FIX], fixes=[FIX], brief=BRIEF, options=OPTS, pr_lines=LINES,
                           order=SECTIONS, summary="The 2N design passes every check.")
    text = _pdf_text(data)
    heads = ["Summary", "Requirements", "Topology options", "Checker findings", "Fixes", "Assumptions ledger",
             "Bill of quantities"]
    assert [text.index(h) for h in heads] == sorted(text.index(h) for h in heads)
    assert "Parallel cable feeder for FA-01" in text and "sqrt3" in text and "§4.6" in text


def test_calc_report_carries_trust_labels():
    data = calc_report_pdf(rev=REV, findings=[FIX], fixes=[FIX], brief=BRIEF, options=OPTS, pr_lines=LINES,
                           order=SECTIONS, summary="The 2N design passes every check.")
    text = _pdf_text(data)
    assert "IEC-based, illustrative values, not for construction" in text
    assert "Demo workspace" in text and "all companies, people and data are fictional" in text


def test_calc_report_numbers_come_from_engine_records():
    summary = "The 2N design passes every check."
    data = calc_report_pdf(rev=REV, findings=[FIX], fixes=[FIX], brief=BRIEF, options=OPTS, pr_lines=LINES,
                           order=SECTIONS, summary=summary)
    text = _pdf_text(data)
    # Every number in the report traces to an engine/verification record: never a number typed into
    # free LLM narration. Rather than checking that a few expected numbers are merely present (which
    # would miss a stray number sneaking in from narration text), parse every number out of the
    # rendered PDF and assert it is a SUBSET of every number present in the engine/verification
    # records that fed the report.
    NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")

    def nums(s: str) -> set[float]:
        return {float(t.replace(",", "")) for t in NUM.findall(s)}

    records = nums(" ".join([summary, REV.model_dump_json(), FIX.model_dump_json(), BRIEF.model_dump_json(),
                             *(o.model_dump_json() for o in OPTS), *(x.model_dump_json() for x in LINES)]))
    assert nums(text) <= records


def test_calc_report_wraps_a_finding_with_many_clauses():
    many_refs = [Citation(doc_id="tender-hall-a", page=i, quote="x", clause=f"§{i}.1") for i in range(1, 21)]
    fix_many = FIX.model_copy(update={"tender_refs": many_refs})
    data = calc_report_pdf(rev=REV, findings=[fix_many], fixes=[fix_many], brief=BRIEF, options=OPTS,
                           pr_lines=LINES, order=SECTIONS, summary="ok")
    text = _pdf_text(data)
    assert "§1.1" in text and "§20.1" in text


def test_calc_report_omits_formula_sentence_when_empty():
    fix_no_formula = FIX.model_copy(update={"formula": ""})
    data = calc_report_pdf(rev=REV, findings=[fix_no_formula], fixes=[fix_no_formula], brief=BRIEF, options=OPTS,
                           pr_lines=LINES, order=SECTIONS, summary="ok")
    text = _pdf_text(data)
    assert "Formula: ." not in text and "Formula:" not in text


def test_requirements_heading_notes_verification_is_per_row():
    data = calc_report_pdf(rev=REV, findings=[FIX], fixes=[FIX], brief=BRIEF, options=OPTS, pr_lines=LINES,
                           order=SECTIONS, summary="ok")
    text = _pdf_text(data)
    assert "Requirements (tender citations; verification shown per row)" in text


def test_blob_exporter_writes_both_files():
    blobs = MemoryBlobStore()
    files = BlobExporter(blobs).export(uid="u1", rev=REV, findings=[FIX], fixes=[FIX], brief=BRIEF, options=OPTS,
                                       pr_lines=LINES, order=SECTIONS, summary="ok")
    assert [f["path"] for f in files] == ["exports/abc-r2/calc-report.pdf", "exports/abc-r2/boq.csv"]
    assert blobs.get("workspaces/u1/exports/abc-r2/calc-report.pdf").startswith(b"%PDF")
    assert blobs.blobs["workspaces/u1/exports/abc-r2/boq.csv"][1] == "text/csv"
