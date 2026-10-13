from pathlib import Path

import pdfplumber
import pytest

from kirchhoff.intake.drawing import DrawingRead, compare_drawing, parse_dxf_geometry
from kirchhoff.intake.render import load_geometry, render_drawing

FIX = Path(__file__).parent / "fixtures"
REPO_GEOMETRY = Path(__file__).resolve().parents[4] / "scenarios" / "hall_a" / "geometry.yaml"


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    out = tmp_path_factory.mktemp("drawing")
    return render_drawing(load_geometry(FIX / "geometry.yaml"), out / "hall.dxf", out / "plan.pdf")


def test_dxf_round_trip_reads_grid_and_overall_size(rendered):
    s = parse_dxf_geometry(rendered[0])
    assert s.grid_x == ["1", "2", "3", "4", "5", "6"]
    assert s.grid_y == ["A", "B", "C", "D"]
    assert s.overall_mm == (60000.0, 36000.0)


def test_pdf_plot_shows_labels_and_overall_dimensions(rendered):
    with pdfplumber.open(rendered[1]) as doc:
        assert len(doc.pages) == 1
        chars = "".join(ch["text"] for ch in doc.pages[0].chars)
    for token in ["60000", "36000", "GA-E-101", "GALLERY", "R6"]:  # no spaces: char joins may drop them
        assert token in chars, token


def test_compare_agrees_when_reading_matches(rendered):
    read = DrawingRead(grid_x=["1", "2", "3", "4", "5", "6"], grid_y=["A", "B", "C", "D"],
                       overall_mm=[60000, 36000])
    result = compare_drawing(read, parse_dxf_geometry(rendered[0]))
    assert result["agrees"] is True and result["differences"] == []


def test_compare_reports_differences(rendered):
    read = DrawingRead(grid_x=["1", "2", "3", "4", "5"], grid_y=["A", "B", "C", "D"], overall_mm=[60000, 30000])
    result = compare_drawing(read, parse_dxf_geometry(rendered[0]))
    assert result["agrees"] is False
    assert any("grid x" in d for d in result["differences"])
    assert any("width" in d for d in result["differences"])


@pytest.mark.skipif(not REPO_GEOMETRY.exists(), reason="WS1 has not written scenarios/hall_a/geometry.yaml yet")
def test_repo_geometry_matches_fixture():
    assert load_geometry(REPO_GEOMETRY) == load_geometry(FIX / "geometry.yaml")
