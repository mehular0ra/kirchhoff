"""Render the Hall A drawing (DXF in mm + PDF plot) from geometry.yaml.

Run from the repo root:
  cd services/api && uv run python ../../scenarios/hall_a/render_drawing.py [--geometry PATH]
"""
import argparse
from pathlib import Path

from kirchhoff.intake.render import load_geometry, render_drawing

HERE = Path(__file__).resolve().parent

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--geometry", type=Path, default=HERE / "geometry.yaml")
    args = ap.parse_args()
    print(*render_drawing(load_geometry(args.geometry), HERE / "out" / "hall-a.dxf", HERE / "out" / "hall-a-plan.pdf"))
