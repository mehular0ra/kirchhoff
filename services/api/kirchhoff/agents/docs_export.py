"""Docs exports. Wed: Exporter protocol + StubExporter. Thu (Task 18): BlobExporter (reportlab PDF + BOQ CSV)."""
import csv
import io
from typing import Protocol
from xml.sax.saxutils import escape

from kirchhoff.agents.fix_text import tidy_tokens
from kirchhoff.agents.trust import fmt_number
from kirchhoff.contracts import DesignBrief, Finding, PRLine, Revision, TopologyOption

SECTIONS = ["summary", "requirements", "options", "findings", "fixes", "ledger", "boq"]

_SYMBOLS = {"√": "sqrt", "Δ": "d", "φ": "phi", "≤": "<=", "≥": ">=", "″": "''", "′": "'", "→": "->", "∥": "||",
            "–": "-", "—": "-", "η": "eta", "μ": "u", "Σ": "sum", "ṁ": "m_dot", "≈": "~", "Ω": "Ohm",
            "−": "-", "ρ": "rho", "π": "pi", "̇": "_dot", "’": "'", "‘": "'", "“": '"', "”": '"', "…": "..."}


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
    cell = ParagraphStyle("c", fontName="Helvetica", fontSize=7.5, leading=9)
    cell_h = ParagraphStyle("ch", fontName="Helvetica-Bold", fontSize=7.5, leading=9)
    TOTAL_W = 178 * mm  # A4 width minus the 16mm left/right margins

    def para(s: object, style=body) -> Paragraph:
        return Paragraph(escape(latin1(s)), style)

    def table(rows: list[list[object]], widths_mm: list[float] | None = None) -> Table:
        n = len(rows[0])
        col_widths = [w * mm for w in widths_mm] if widths_mm else [TOTAL_W / n] * n
        # Cells are Paragraphs (not bare strings) with explicit column widths, so long text (e.g. a
        # finding with many cited clauses) wraps instead of overflowing or stretching the table.
        data = [[Paragraph(escape(latin1("" if c is None else c)), cell_h if i == 0 else cell)
                 for c in r] for i, r in enumerate(rows)]
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    reqs = brief.requirements if brief else []
    ordered = sorted(findings, key=lambda f: (f.status != "fail", f.rule_id, f.element_id))

    def fix_text(f: Finding) -> str:
        # Engine tier ids read as words ("pipe_low" -> "the low pipe tier"), as in the drawer and the co-pilot.
        s = tidy_tokens(f"{f.id}: {f.fix['label']} ({f.fix.get('agent', '')}). {f.fix.get('reason', '')}")
        if f.formula:
            s += f" Formula: {f.formula}."
        if f.rejected_fix:
            s += f" Rejected: {tidy_tokens(f.rejected_fix['label'])}."
        return s

    sections = {
        "summary": lambda: [para("Summary", h2), para(summary), para(
            f"Revision {rev.id} · hash {rev.hash} · " + ", ".join(f"{k} {v}" for k, v in rev.check_summary.items()))],
        "requirements": lambda: [para("Requirements (tender citations; verification shown per row)", h2), table(
            [["Id", "Clause", "Page", "Value", "Unit", "Verified"]]
            + [[r.id, r.citation.clause, r.citation.page,
                fmt_number(r.value) if isinstance(r.value, float) else r.value, r.unit,
                "yes" if r.verified else "no"]
               for r in reqs], widths_mm=[40, 24, 16, 20, 16, 62])],
        "options": lambda: [para("Topology options", h2), table(
            [["Option", "Installed MVA", "Normal %", "Failover %", "Cost USD", "Losses kW", "Max lead (wk)", "SPOF"]]
            + [[o.id, fmt_number(o.installed_mva), fmt_number(o.normal_loading_pct),
                fmt_number(o.failover_loading_pct), fmt_number(o.cost), fmt_number(o.losses_kw),
                fmt_number(o.max_lead_time_weeks), fmt_number(o.spof_count)] for o in options])],
        "findings": lambda: [para("Checker findings", h2), table(
            [["Rule", "Element", "Status", "Value", "Limit", "Unit", "Clauses"]]
            + [[f.rule_id, f.element_id, f.status, fmt_number(f.value), fmt_number(f.limit), f.unit,
                ", ".join(c.clause for c in f.tender_refs if c.clause)] for f in ordered],
            widths_mm=[18, 20, 16, 16, 16, 12, 80])],
        "fixes": lambda: [para("Fixes", h2)] + ([para(fix_text(f)) for f in fixes]
            or [para("No fixes were needed.")]),
        "ledger": lambda: [para("Assumptions ledger", h2)] + [para(f"[{e.kind}] {e.text}") for e in rev.ledger],
        "boq": lambda: [para("Bill of quantities", h2), table(
            [["Material", "Description", "Qty", "Unit price USD", "Lead (wk)"]]
            + [[x.material_id, x.description, x.qty, f"{x.unit_price:,.2f}", x.lead_time_weeks] for x in pr_lines],
            widths_mm=[26, 70, 20, 36, 26])],
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
