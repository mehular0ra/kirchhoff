"""Renders the scenario documents (tender PDF here; hall drawing added in Task 2). No LLM."""
from pathlib import Path
from xml.sax.saxutils import escape

from .tender_schema import TenderDoc


def render_tender_pdf(tender: TenderDoc, out: Path) -> Path:
    from reportlab import rl_config

    rl_config.invariant = 1  # deterministic bytes (no timestamps / random ids)
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    title_s = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=16, leading=20, spaceAfter=6)
    meta_s = ParagraphStyle("m", fontName="Helvetica", fontSize=9.5, leading=13, textColor="#444444")
    head_s = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=10,
                            spaceAfter=3, alignment=TA_LEFT)
    body_s = ParagraphStyle("b", fontName="Helvetica", fontSize=10, leading=14, alignment=TA_LEFT)

    story = [Paragraph(escape(tender.title), title_s), Paragraph(escape(f"Client: {tender.client}"), meta_s)]
    if tender.site:
        story.append(Paragraph(escape(f"Site: {tender.site}"), meta_s))
    story.append(Paragraph(escape(f"Reference: {tender.reference}"), meta_s))
    story.append(Paragraph(escape(tender.notice or "Fictional tender authored for the Kirchhoff demo."), meta_s))
    story.append(Spacer(1, 8 * mm))
    page = 1
    for c in tender.clauses:
        while page < c.page:
            story.append(PageBreak())
            page += 1
        story.append(Paragraph(escape(f"{c.id}  {c.title}"), head_s))
        story.append(Paragraph(escape(c.text), body_s))

    def footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(22 * mm, 12 * mm, f"{tender.reference} · {tender.client} · Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(out), pagesize=A4, title=tender.title, author=tender.client,
                            leftMargin=22 * mm, rightMargin=22 * mm, topMargin=22 * mm, bottomMargin=22 * mm)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out
