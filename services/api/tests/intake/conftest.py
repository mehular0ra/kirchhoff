from pathlib import Path

import pytest

from kirchhoff.intake.render import render_tender_pdf
from kirchhoff.intake.tender_schema import load_tender

FIX = Path(__file__).parent / "fixtures"
GROUND_TRUTH = Path(__file__).resolve().parents[4] / "scenarios" / "hall_a" / "ground_truth.yaml"


@pytest.fixture(scope="session")
def tender():
    return load_tender(FIX / "tender.yaml")


@pytest.fixture(scope="session")
def tender_pdf(tmp_path_factory, tender) -> Path:
    return render_tender_pdf(tender, tmp_path_factory.mktemp("tender") / "tender-hall-a.pdf")


@pytest.fixture(scope="session")
def ground_truth_path() -> Path:
    return GROUND_TRUTH
