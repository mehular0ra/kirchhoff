"""Small deterministic documents for the demo world (ruling W10): a one-page summary PDF and a BOQ CSV.
reportlab runs with invariant=1, so identical inputs give identical bytes."""
import csv
import io
from xml.sax.saxutils import escape

from kirchhoff.contracts import PRLine

from ..model import FICTIONAL_NOTICE, ILLUSTRATIVE

_SUBST = {"·": "-", "—": "-", "–": "-", "≤": "<=", "≥": ">=", "Δ": "d", "→": "->"}


def _latin1(s: object) -> str:
    text = "".join(_SUBST.get(ch, ch) for ch in str(s))
    return text.encode("latin-1", "replace").decode("latin-1")


def summary_pdf(title: str, subtitle: str, rows: list[tuple[str, str]]) -> bytes:
    from reportlab import rl_config

    rl_config.invariant = 1
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=15, leading=19, spaceAfter=4)
    body = ParagraphStyle("b", fontName="Helvetica", fontSize=9, leading=12)
    note = ParagraphStyle("n", fontName="Helvetica-Oblique", fontSize=8, leading=10, textColor=colors.grey)
    table = Table([["Item", "Value"]] + [[_latin1(k), _latin1(v)] for k, v in rows],
                  colWidths=[60 * mm, 110 * mm], repeatRows=1)
    table.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 8.5),
                               ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
                               ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story = [Paragraph(escape(_latin1(title)), h1), Paragraph(escape(_latin1(subtitle)), body), Spacer(1, 4 * mm),
             table, Spacer(1, 6 * mm), Paragraph(escape(_latin1(ILLUSTRATIVE)), note),
             Paragraph(escape(_latin1(FICTIONAL_NOTICE)), note)]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, title=_latin1(title), author="Kirchhoff demo world", leftMargin=18 * mm,
                      rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm).build(story)
    return buf.getvalue()


def boq_csv_bytes(lines: list[PRLine]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["material_id", "description", "qty", "unit_price_usd", "line_total_usd", "lead_time_weeks"])
    for x in lines:
        w.writerow([x.material_id, x.description, x.qty, f"{x.unit_price:.2f}", f"{x.qty * x.unit_price:.2f}",
                    x.lead_time_weeks])
    return buf.getvalue().encode("utf-8")
