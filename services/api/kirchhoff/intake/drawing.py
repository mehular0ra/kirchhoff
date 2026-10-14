"""Drawing cross-check: Gemini reads the PDF plot; the DXF is parsed deterministically; code compares."""
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class DrawingRead(BaseModel):
    grid_x: list[str]
    grid_y: list[str]
    overall_mm: list[float]  # [length along x, width along y]


class DxfSummary(BaseModel):
    grid_x: list[str]
    grid_y: list[str]
    overall_mm: tuple[float, float]


def parse_dxf_geometry(path: Path | str) -> DxfSummary:
    import ezdxf

    msp = ezdxf.readfile(str(path)).modelspace()

    def labels(layer: str, axis: int) -> list[str]:
        items = []
        for t in msp.query(f'TEXT[layer=="{layer}"]'):
            _, point, _ = t.get_placement()
            items.append((point[axis], t.dxf.text))
        return [text for _, text in sorted(items)]

    pts = list(msp.query('LWPOLYLINE[layer=="HALL"]').first.get_points("xy"))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return DxfSummary(grid_x=labels("GRID_X", 0), grid_y=labels("GRID_Y", 1),
                      overall_mm=(round(max(xs) - min(xs), 1), round(max(ys) - min(ys), 1)))


def compare_drawing(read: DrawingRead, dxf: DxfSummary, tol_mm: float = 50.0) -> dict[str, Any]:
    diffs: list[str] = []
    if sorted(read.grid_x) != sorted(dxf.grid_x):
        diffs.append(f"grid x labels: drawing {', '.join(read.grid_x)} vs DXF {', '.join(dxf.grid_x)}")
    if sorted(read.grid_y) != sorted(dxf.grid_y):
        diffs.append(f"grid y labels: drawing {', '.join(read.grid_y)} vs DXF {', '.join(dxf.grid_y)}")
    if len(read.overall_mm) != 2:
        diffs.append("overall dimensions not read from the drawing")
    else:
        for name, a, b in zip(("length", "width"), read.overall_mm, dxf.overall_mm):
            if abs(a - b) > tol_mm:
                diffs.append(f"overall {name}: drawing {a:.0f} mm vs DXF {b:.0f} mm")
    return {"agrees": not diffs, "differences": diffs, "grid_x": dxf.grid_x, "grid_y": dxf.grid_y,
            "overall_mm": list(dxf.overall_mm)}
