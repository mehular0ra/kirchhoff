"""Renders the scenario documents (tender PDF here; hall drawing added in Task 2). No LLM."""
from pathlib import Path
from xml.sax.saxutils import escape

import yaml
from pydantic import BaseModel, ConfigDict

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


MM = 1000.0  # DXF drawing units are millimetres; geometry.yaml is in metres
Rect4 = tuple[float, float, float, float]  # x0, y0, x1, y1


class _Loose(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Columns(_Loose):
    xs: list[float]
    ys: list[float]


class KeepoutSpec(_Loose):
    id: str
    name: str = ""
    rect: Rect4


class RoomSpec(_Loose):
    rect: Rect4


class RowSpec(_Loose):
    id: str
    x: float
    zone: str | None = None


class RackSpec(_Loose):
    per_row: int = 8
    w: float = 0.6
    d: float = 1.2
    y_south: float
    y_north: float


class HallGeometry(_Loose):
    hall: Rect4
    columns: Columns
    keepouts: list[KeepoutSpec] = []
    rooms: dict[str, RoomSpec] = {}
    gallery: Rect4 | None = None
    rows: list[RowSpec]
    racks: RackSpec

    def labels_x(self) -> list[str]:
        return [str(i + 1) for i in range(len(self.columns.xs))]

    def labels_y(self) -> list[str]:
        return [chr(ord("A") + i) for i in range(len(self.columns.ys))]


def load_geometry(path: Path | str) -> HallGeometry:
    return HallGeometry.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def _rack_rects(g: HallGeometry, row: RowSpec) -> list[Rect4]:
    pitch = (g.racks.y_north - g.racks.y_south) / g.racks.per_row
    half = g.racks.d / 2
    return [(row.x - half, g.racks.y_south + i * pitch, row.x + half, g.racks.y_south + (i + 1) * pitch)
            for i in range(g.racks.per_row)]


def _mid(r: Rect4) -> tuple[float, float]:
    return (r[0] + r[2]) / 2, (r[1] + r[3]) / 2


def _write_dxf(g: HallGeometry, out: Path) -> None:
    import ezdxf
    from ezdxf.enums import TextEntityAlignment

    # Deterministic bytes across re-renders of the same input: without this, ezdxf stamps
    # $TDCREATE/$TDUCREATE/$TDUPDATE/$TDUUPDATE with the current time and $FINGERPRINTGUID/
    # $VERSIONGUID with random GUIDs on every save (and an "ezdxf <ver> @ <timestamp>" metadata
    # marker). ezdxf's own fixed-metadata mode pins all of these (and $HANDSEED/$TDINDWG/
    # $TDUSRTIMER, which are otherwise already static) to constant values.
    ezdxf.options.write_fixed_meta_data_for_testing = True

    doc = ezdxf.new("R2018", setup=True)
    doc.units = ezdxf.units.MM
    for name, color in [("HALL", 7), ("COLUMNS", 8), ("GRID", 9), ("GRID_X", 7), ("GRID_Y", 7), ("KEEPOUT", 1),
                        ("ROOMS", 3), ("RACKS", 4), ("CDU", 5), ("DIMS", 2)]:
        doc.layers.add(name, color=color)
    msp = doc.modelspace()

    def rect(r: Rect4, layer: str) -> None:
        x0, y0, x1, y1 = (v * MM for v in r)
        msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs={"layer": layer})

    def text(s: str, x: float, y: float, layer: str, h: float = 800.0, rotation: float = 0.0) -> None:
        msp.add_text(s, height=h, rotation=rotation, dxfattribs={"layer": layer}).set_placement(
            (x * MM, y * MM), align=TextEntityAlignment.MIDDLE_CENTER)

    xs, ys = g.columns.xs, g.columns.ys
    rect(g.hall, "HALL")
    for x in xs:
        for y in ys:
            rect((x - 0.3, y - 0.3, x + 0.3, y + 0.3), "COLUMNS")
    for x, lab in zip(xs, g.labels_x()):
        msp.add_line((x * MM, (min(ys) - 3.6) * MM), (x * MM, (max(ys) + 1.5) * MM),
                     dxfattribs={"layer": "GRID", "linetype": "DASHED"})
        msp.add_circle((x * MM, (min(ys) - 4.5) * MM), 900, dxfattribs={"layer": "GRID"})
        text(lab, x, min(ys) - 4.5, "GRID_X")
    for y, lab in zip(ys, g.labels_y()):
        msp.add_line(((min(xs) - 3.6) * MM, y * MM), ((max(xs) + 1.5) * MM, y * MM),
                     dxfattribs={"layer": "GRID", "linetype": "DASHED"})
        msp.add_circle(((min(xs) - 4.5) * MM, y * MM), 900, dxfattribs={"layer": "GRID"})
        text(lab, min(xs) - 4.5, y, "GRID_Y")
    for k in g.keepouts:
        rect(k.rect, "KEEPOUT")
        text(k.id, *_mid(k.rect), "KEEPOUT", h=500)
    for name, room in g.rooms.items():
        rect(room.rect, "ROOMS")
        text(f"LV ROOM {name}", *_mid(room.rect), "ROOMS", h=500)
    for row in g.rows:
        for rr in _rack_rects(g, row):
            rect(rr, "RACKS")
        text(row.id, row.x, g.racks.y_north + 0.9, "RACKS", h=500)
    if g.gallery:
        rect(g.gallery, "CDU")
        text("CDU GALLERY", *_mid(g.gallery), "CDU", h=500)
    x0, y0, x1, y1 = g.hall
    msp.add_line((x0 * MM, (min(ys) - 7) * MM), (x1 * MM, (min(ys) - 7) * MM), dxfattribs={"layer": "DIMS"})
    text(f"{(x1 - x0) * MM:.0f}", (x0 + x1) / 2, min(ys) - 8, "DIMS")
    msp.add_line(((min(xs) - 7) * MM, y0 * MM), ((min(xs) - 7) * MM, y1 * MM), dxfattribs={"layer": "DIMS"})
    text(f"{(y1 - y0) * MM:.0f}", min(xs) - 8, (y0 + y1) / 2, "DIMS", rotation=90)

    # ezdxf's own required-class resolution (invoked again internally on save) iterates a
    # `set[str]` of the DXF types in use, so the CLASSES section's entry order (e.g. LAYOUT vs.
    # ACDBPLACEHOLDER) otherwise depends on Python's per-process string hash randomization, not
    # on this function's input. Registering the classes once here and sorting them pins that
    # order; saveas()'s internal re-registration is then a no-op (register() skips existing keys).
    doc.classes.add_required_classes(doc.dxfversion)
    doc.classes.classes = dict(sorted(doc.classes.classes.items()))
    doc.saveas(str(out))


def _write_plot(g: HallGeometry, out: Path) -> None:
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.pdfgen import canvas

    W, H = landscape(A3)
    rects = [g.hall] + [r.rect for r in g.rooms.values()]
    minx, maxx = min(r[0] for r in rects) - 10, max(r[2] for r in rects) + 4
    miny, maxy = min(r[1] for r in rects) - 10, max(r[3] for r in rects) + 4
    s = min((W - 80) / (maxx - minx), (H - 140) / (maxy - miny))

    def P(x: float, y: float) -> tuple[float, float]:
        return 40 + (x - minx) * s, 90 + (y - miny) * s

    c = canvas.Canvas(str(out), pagesize=(W, H), invariant=1)

    def rect(r: Rect4, width: float = 0.8) -> None:
        (ax, ay), (bx, by) = P(r[0], r[1]), P(r[2], r[3])
        c.setLineWidth(width)
        c.rect(ax, ay, bx - ax, by - ay)

    xs, ys = g.columns.xs, g.columns.ys
    rect(g.hall, 1.6)
    c.setDash(6, 3)
    for x in xs:
        c.line(*P(x, min(ys) - 3.6), *P(x, max(ys) + 1.5))
    for y in ys:
        c.line(*P(min(xs) - 3.6, y), *P(max(xs) + 1.5, y))
    c.setDash()
    c.setFont("Helvetica-Bold", 11)
    for x, lab in zip(xs, g.labels_x()):
        px, py = P(x, min(ys) - 4.5)
        c.circle(px, py, 10)
        c.drawCentredString(px, py - 4, lab)
    for y, lab in zip(ys, g.labels_y()):
        px, py = P(min(xs) - 4.5, y)
        c.circle(px, py, 10)
        c.drawCentredString(px, py - 4, lab)
    for x in xs:
        for y in ys:
            rect((x - 0.3, y - 0.3, x + 0.3, y + 0.3), 0.6)
    c.setFont("Helvetica", 8)
    for k in g.keepouts:
        rect(k.rect)
        c.drawCentredString(*P(*_mid(k.rect)), f"{k.id} {k.name}".strip().upper())
    for name, room in g.rooms.items():
        rect(room.rect)
        c.drawCentredString(*P(*_mid(room.rect)), f"LV ROOM {name}")
    for row in g.rows:
        for rr in _rack_rects(g, row):
            rect(rr, 0.4)
        c.drawCentredString(*P(row.x, g.racks.y_north + 0.9), row.id)
    if g.gallery:
        rect(g.gallery)
        c.drawCentredString(*P(*_mid(g.gallery)), "CDU GALLERY")
    x0, y0, x1, y1 = g.hall
    c.setFont("Helvetica-Bold", 10)
    c.line(*P(x0, min(ys) - 7), *P(x1, min(ys) - 7))
    c.drawCentredString(*P((x0 + x1) / 2, min(ys) - 8.2), f"{(x1 - x0) * MM:.0f}")
    c.line(*P(min(xs) - 7, y0), *P(min(xs) - 7, y1))
    vx, vy = P(min(xs) - 8.2, (y0 + y1) / 2)
    c.saveState()
    c.translate(vx, vy)
    c.rotate(90)
    c.drawCentredString(0, 0, f"{(y1 - y0) * MM:.0f}")
    c.restoreState()
    c.setFont("Helvetica", 9)
    c.drawString(40, 40, "DWG GA-E-101 Rev C · AI data hall general arrangement · Dimensions in mm · "
                         "Deccan Compute (fictional) · Not for construction")
    c.showPage()
    c.save()


def render_drawing(geom: HallGeometry, dxf_out: Path, pdf_out: Path) -> tuple[Path, Path]:
    dxf_out, pdf_out = Path(dxf_out), Path(pdf_out)
    dxf_out.parent.mkdir(parents=True, exist_ok=True)
    pdf_out.parent.mkdir(parents=True, exist_ok=True)
    _write_dxf(geom, dxf_out)
    _write_plot(geom, pdf_out)
    return dxf_out, pdf_out
