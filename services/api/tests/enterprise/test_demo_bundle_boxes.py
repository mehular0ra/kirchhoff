"""Issue #14 (follow-up to #11): no citation shipped in a demo bundle may lack its PDF highlight. A finding's tender_ref
with a quote and a page must carry a bbox, and the box must be where pdfplumber finds that quote on the real tender."""
import json
from pathlib import Path

import pytest

from kirchhoff.contracts import ProjectBundle
from kirchhoff.intake.verify import PdfText

REPO = Path(__file__).resolve().parents[4]
BUNDLES = sorted((REPO / "apps" / "web" / "public" / "demo" / "projects").glob("*.json"))
TENDER = REPO / "scenarios" / "hall_a" / "out" / "tender-hall-a.pdf"


def citations(node):
    """Every citation-shaped dict: page + quote + bbox, wherever it sits in the bundle."""
    if isinstance(node, dict):
        if {"page", "quote", "bbox"} <= node.keys():
            yield node
        for v in node.values():
            yield from citations(v)
    elif isinstance(node, list):
        for v in node:
            yield from citations(v)


def test_the_demo_world_ships_the_bundles_this_test_guards():
    assert {p.stem for p in BUNDLES} >= {"hall-a", "pune-edge-1", "vindhya-lv", "grid-132kv", "solar-5mwp"}


@pytest.mark.parametrize("path", BUNDLES, ids=lambda p: p.stem)
def test_no_citation_with_a_quote_and_a_page_lacks_a_box(path):
    cited = [c for c in citations(json.loads(path.read_text(encoding="utf-8"))) if c["quote"] and c["page"]]
    missing = [c for c in cited if not c["bbox"]]
    assert not missing, f"{path.stem}: {len(missing)} of {len(cited)} citations have no bbox, e.g. {missing[0]}"


def test_boxed_what_ifs_adds_the_tender_box_to_what_ifs_from_the_real_engine():
    """The what-if chips (precomputed here, live in /api/what-if) cite the tender like any finding; the engine gives
    quotes without boxes, and boxed_what_ifs puts pdfplumber's box on each one."""
    from kirchhoff.engine import api as engine
    from kirchhoff.enterprise.world.projects import boxed_what_ifs, chip_what_ifs

    scn = engine.load_scenario("hall_a", REPO / "scenarios")
    model = ProjectBundle.model_validate_json(BUNDLES[[p.stem for p in BUNDLES].index("hall-a")].read_text(
        encoding="utf-8")).revisions[-1].model
    raw = chip_what_ifs(engine, scn, model, engine.default_erp(), "seed:hall-a@r2", required=True)
    before = [c for w in raw for f in w.findings for c in f.tender_refs if c.quote and c.page]
    assert before and not any(c.bbox for c in before)
    after = [c for w in boxed_what_ifs(raw, TENDER) for f in w.findings for c in f.tender_refs if c.quote and c.page]
    assert len(after) == len(before)
    with PdfText(TENDER) as pdf:
        for c in after:
            assert c.bbox is not None and tuple(c.bbox) == tuple(pdf.find_bbox(c.page, c.quote)), (c.page, c.quote)


@pytest.mark.parametrize("path", [p for p in BUNDLES if p.stem in ("hall-a", "pune-edge-1")], ids=lambda p: p.stem)
def test_each_box_is_where_the_quote_is_on_the_real_tender(path):
    cited = [c for c in citations(json.loads(path.read_text(encoding="utf-8"))) if c["quote"] and c["page"]]
    assert cited, "an engine-built data hall bundle cites the tender"
    with PdfText(TENDER) as pdf:
        for page, quote in sorted({(c["page"], c["quote"]) for c in cited}):
            found = pdf.find_bbox(page, quote)
            assert found is not None, f"p.{page}: the quote is not on the page: {quote!r}"
            boxes = {tuple(c["bbox"]) for c in cited if (c["page"], c["quote"]) == (page, quote)}
            assert boxes == {tuple(found)}, f"p.{page}: {quote!r}"
