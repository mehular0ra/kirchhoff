"""Docs exports. Wed: Exporter protocol + StubExporter. Thu (Task 18): BlobExporter (reportlab PDF + BOQ CSV)."""
import csv
import io
from typing import Protocol
from xml.sax.saxutils import escape

from kirchhoff.contracts import DesignBrief, Finding, PRLine, Revision, TopologyOption

SECTIONS = ["summary", "requirements", "options", "findings", "fixes", "ledger", "boq"]

_SYMBOLS = {"√": "sqrt", "Δ": "d", "φ": "phi", "≤": "<=", "≥": ">=", "″": "''", "′": "'", "→": "->", "∥": "||",
            "–": "-", "—": "-", "η": "eta", "μ": "u", "Σ": "sum", "ṁ": "m_dot", "≈": "~", "Ω": "Ohm"}


class Exporter(Protocol):
    def export(self, *, uid: str, rev: Revision, findings: list[Finding], fixes: list[Finding],
               brief: DesignBrief | None, options: list[TopologyOption], pr_lines: list[PRLine], order: list[str],
               summary: str) -> list[dict]: ...


class StubExporter:
    def export(self, **_: object) -> list[dict]:
        return [{"name": "calc-report.pdf", "path": None, "status": "pending"},
                {"name": "boq.csv", "path": None, "status": "pending"}]


def latin1(s: object) -> str:
    text = "".join(_SYMBOLS.get(ch, ch) for ch in str(s))
    return text.encode("latin-1", "replace").decode("latin-1")


def boq_csv(lines: list[PRLine]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["material_id", "description", "qty", "unit_price_usd", "line_total_usd", "lead_time_weeks"])
    for x in lines:
        w.writerow([x.material_id, x.description, x.qty, f"{x.unit_price:.2f}", f"{x.qty * x.unit_price:.2f}",
                    x.lead_time_weeks])
    w.writerow(["TOTAL", "", sum(x.qty for x in lines), "", f"{sum(x.qty * x.unit_price for x in lines):.2f}",
                max((x.lead_time_weeks for x in lines), default=0)])
    return buf.getvalue().encode("utf-8")


def calc_report_pdf(*, rev: Revision, findings: list[Finding], fixes: list[Finding], brief: DesignBrief | None,
                    options: list[TopologyOption], pr_lines: list[PRLine], order: list[str], summary: str) -> bytes:
    from reportlab import rl_config

    rl_config.invariant = 1
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=15, leading=19, spaceAfter=6)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11.5, leading=15, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("b", fontName="Helvetica", fontSize=9, leading=12)
    trust = ParagraphStyle("t", fontName="Helvetica-Oblique", fontSize=8, leading=11, textColor=colors.grey)

    def para(s: object, style=body) -> Paragraph:
        return Paragraph(escape(latin1(s)), style)

    def table(rows: list[list[object]]) -> Table:
        t = Table([[latin1("" if c is None else c) for c in r] for r in rows], repeatRows=1)
        t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 7.5),
                               ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.5),
                               ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    reqs = brief.requirements if brief else []
    ordered = sorted(findings, key=lambda f: (f.status != "fail", f.rule_id, f.element_id))
    sections = {
        "summary": lambda: [para("Summary", h2), para(summary), para(
            f"Revision {rev.id} · hash {rev.hash} · " + ", ".join(f"{k} {v}" for k, v in rev.check_summary.items()))],
        "requirements": lambda: [para("Requirements (verified tender citations)", h2), table(
            [["Id", "Clause", "Page", "Value", "Unit", "Verified"]]
            + [[r.id, r.citation.clause, r.citation.page, r.value, r.unit, "yes" if r.verified else "no"]
               for r in reqs])],
        "options": lambda: [para("Topology options", h2), table(
            [["Option", "Installed MVA", "Normal %", "Failover %", "Cost USD", "Losses kW", "Max lead (wk)", "SPOF"]]
            + [[o.id, o.installed_mva, o.normal_loading_pct, o.failover_loading_pct, f"{o.cost:,.0f}", o.losses_kw,
                o.max_lead_time_weeks, o.spof_count] for o in options])],
        "findings": lambda: [para("Checker findings", h2), table(
            [["Rule", "Element", "Status", "Value", "Limit", "Unit", "Clauses"]]
            + [[f.rule_id, f.element_id, f.status, f.value, f.limit, f.unit,
                ", ".join(c.clause for c in f.tender_refs if c.clause)] for f in ordered])],
        "fixes": lambda: [para("Fixes", h2)] + ([para(
            f"{f.id}: {f.fix['label']} ({f.fix.get('agent', '')}). {f.fix.get('reason', '')} Formula: {f.formula}."
            + (f" Rejected: {f.rejected_fix['label']}." if f.rejected_fix else "")) for f in fixes]
            or [para("No fixes were needed.")]),
        "ledger": lambda: [para("Assumptions ledger", h2)] + [para(f"[{e.kind}] {e.text}") for e in rev.ledger],
        "boq": lambda: [para("Bill of quantities", h2), table(
            [["Material", "Description", "Qty", "Unit price USD", "Lead (wk)"]]
            + [[x.material_id, x.description, x.qty, f"{x.unit_price:,.2f}", x.lead_time_weeks] for x in pr_lines])],
    }
    story = [para("Kirchhoff calc report", h1),
             para("IEC-based, illustrative values, not for construction. Every number comes from the "
                  "deterministic engine; text was checked against the digit allowlist.", trust),
             para("Demo workspace — all companies, people and data are fictional.", trust)]
    for name in order:
        story += sections[name]()
        story.append(Spacer(1, 3 * mm))
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, title=f"Calc report {rev.id}", leftMargin=16 * mm, rightMargin=16 * mm,
                      topMargin=16 * mm, bottomMargin=16 * mm).build(story)
    return buf.getvalue()


class BlobExporter:
    def __init__(self, blobs) -> None:
        self.blobs = blobs

    def export(self, *, uid: str, rev: Revision, findings: list[Finding], fixes: list[Finding],
               brief: DesignBrief | None, options: list[TopologyOption], pr_lines: list[PRLine], order: list[str],
               summary: str) -> list[dict]:
        base = f"exports/{rev.id}"
        pdf = calc_report_pdf(rev=rev, findings=findings, fixes=fixes, brief=brief, options=options,
                              pr_lines=pr_lines, order=order, summary=summary)
        self.blobs.put(f"workspaces/{uid}/{base}/calc-report.pdf", pdf, "application/pdf")
        self.blobs.put(f"workspaces/{uid}/{base}/boq.csv", boq_csv(pr_lines), "text/csv")
        return [{"name": "calc-report.pdf", "path": f"{base}/calc-report.pdf", "status": "ready",
                 "content_type": "application/pdf"},
                {"name": "boq.csv", "path": f"{base}/boq.csv", "status": "ready", "content_type": "text/csv"}]
