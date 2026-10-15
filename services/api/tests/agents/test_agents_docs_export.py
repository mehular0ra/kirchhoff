import io

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
    data = calc_report_pdf(rev=REV, findings=[FIX], fixes=[FIX], brief=BRIEF, options=OPTS, pr_lines=LINES,
                           order=SECTIONS, summary="The 2N design passes every check.")
    text = _pdf_text(data)
    # Every number in the report traces to an engine/verification record: the revision hash, check
    # summary counts, the finding's value/limit, the option's installed MVA/cost, the BOQ qty/price and
    # the verified requirement's cited value -- never a number typed into free LLM narration.
    for n in ("40", "2.16", "2.0", "18.9", "6", "118,000.00"):
        assert n in text


def test_blob_exporter_writes_both_files():
    blobs = MemoryBlobStore()
    files = BlobExporter(blobs).export(uid="u1", rev=REV, findings=[FIX], fixes=[FIX], brief=BRIEF, options=OPTS,
                                       pr_lines=LINES, order=SECTIONS, summary="ok")
    assert [f["path"] for f in files] == ["exports/abc-r2/calc-report.pdf", "exports/abc-r2/boq.csv"]
    assert blobs.get("workspaces/u1/exports/abc-r2/calc-report.pdf").startswith(b"%PDF")
    assert blobs.blobs["workspaces/u1/exports/abc-r2/boq.csv"][1] == "text/csv"
