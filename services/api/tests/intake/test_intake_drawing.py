import subprocess
import sys
import time
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


def test_dxf_is_byte_identical_across_rerenders(tmp_path):
    geom = load_geometry(FIX / "geometry.yaml")
    dxf1, _ = render_drawing(geom, tmp_path / "run1" / "hall.dxf", tmp_path / "run1" / "plan.pdf")
    time.sleep(1.1)  # cross a wall-clock second so a time-based regression would actually show up
    dxf2, _ = render_drawing(geom, tmp_path / "run2" / "hall.dxf", tmp_path / "run2" / "plan.pdf")
    assert dxf1.read_bytes() == dxf2.read_bytes()


def test_dxf_is_byte_identical_across_separate_processes(tmp_path):
    # In-process re-renders share one interpreter's (and thus one PYTHONHASHSEED's) string hash
    # order, which would hide a regression where a `set[str]` iteration (e.g. ezdxf's internal
    # CLASSES-section bookkeeping) leaks into the byte stream. Two separate interpreter
    # invocations get independently-randomized hash seeds by default, so this exercises that path.
    script = (
        "from pathlib import Path\n"
        "from kirchhoff.intake.render import load_geometry, render_drawing\n"
        f"render_drawing(load_geometry(r'{FIX / 'geometry.yaml'}'), Path(r'{{0}}'), Path(r'{{1}}'))\n"
    )
    for i in (1, 2):
        dxf_path = tmp_path / f"p{i}" / "hall.dxf"
        pdf_path = tmp_path / f"p{i}" / "plan.pdf"
        subprocess.run([sys.executable, "-c", script.format(dxf_path, pdf_path)], check=True)
    assert (tmp_path / "p1" / "hall.dxf").read_bytes() == (tmp_path / "p2" / "hall.dxf").read_bytes()
