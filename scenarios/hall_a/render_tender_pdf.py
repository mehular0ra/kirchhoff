"""Render the Hall A tender PDF from tender.yaml.

Run from the repo root:
  cd services/api && uv run python ../../scenarios/hall_a/render_tender_pdf.py [--tender PATH]
"""
import argparse
from pathlib import Path

from kirchhoff.intake.render import render_tender_pdf
from kirchhoff.intake.tender_schema import load_tender

HERE = Path(__file__).resolve().parent

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tender", type=Path, default=HERE / "tender.yaml")
    ap.add_argument("--out", type=Path, default=HERE / "out" / "tender-hall-a.pdf")
    args = ap.parse_args()
    print(render_tender_pdf(load_tender(args.tender), args.out))
