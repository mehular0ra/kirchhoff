"""Spatial checks with Shapely (spec §8.2): a pipe segment is "above electrical" if its tier is higher than the
busway tier and its plan projection intersects an electrical run's footprint; column clearance; and solid
clash detection (3D intersections only)."""
from shapely.geometry import LineString, Point, box

from kirchhoff.contracts import DesignModel, Pipe
from kirchhoff.contracts.extra import ClashReport

BUSWAY_WIDTH_M = 0.2
BUSWAY_HEIGHT_M = 0.15
COLUMN_SIZE_M = 0.4
RACK_HEIGHT_M = 2.3
PIPE_OD_MM = {100: 114.3, 150: 168.3, 200: 219.1}


def _plan(points: list[tuple[float, float]]):
    pts = [points[0]] + [p for prev, p in zip(points, points[1:]) if p != prev]
    return Point(pts[0]) if len(pts) == 1 else LineString(pts)


def electrical_runs(model: DesignModel) -> list[tuple[str, list[tuple[float, float]], float]]:
    """(id, plan polyline, z) for row busways and routed feeders (busway or cable)."""
    z_bus = float(model.geometry.tiers["busway"])
    runs = []
    for e in model.equipment:
        if e.kind == "busway" and "x0" in e.params:
            p = e.params
            runs.append((e.id, [(float(p["x0"]), float(p["y0"])), (float(p["x1"]), float(p["y1"]))],
                         float(p.get("z", z_bus))))
    for c in model.connections:
        if c.kind in ("busway", "cable") and c.route:
            runs.append((c.id, [(p.x, p.y) for p in c.route], c.route[0].z))
    return sorted(runs)


def footprint(points: list[tuple[float, float]]):
    return _plan(points).buffer(BUSWAY_WIDTH_M / 2.0, cap_style="flat")


def column_boxes(model: DesignModel):
    h = COLUMN_SIZE_M / 2.0
    return [box(x - h, y - h, x + h, y + h) for x, y in model.geometry.columns]


def segments(pipe: Pipe):
    return list(zip(pipe.route, pipe.route[1:]))


def pipe_crossings(model: DesignModel, pipe: Pipe) -> list[dict]:
    """Electrical runs that this pipe passes above: [{"run": id, "at": [x, y, z]}], one entry per run."""
    tier = float(model.geometry.tiers["busway"])
    runs = [(rid, footprint(pts)) for rid, pts, _z in electrical_runs(model)]
    found: dict[str, dict] = {}
    for a, b in segments(pipe):
        z = max(a.z, b.z)
        if z <= tier + 1e-6:
            continue
        plan = _plan([(a.x, a.y), (b.x, b.y)])
        for rid, fp in runs:
            if rid not in found and plan.intersects(fp):
                c = plan.intersection(fp).centroid
                found[rid] = {"run": rid, "at": [round(c.x, 3), round(c.y, 3), z]}
    return [found[k] for k in sorted(found)]


def column_clearance_m(model: DesignModel, pipe: Pipe) -> float:
    plan = _plan([(p.x, p.y) for p in pipe.route])
    return min((plan.distance(col) for col in column_boxes(model)), default=float("inf"))


def detect_clashes(model: DesignModel) -> ClashReport:
    """Solid intersections only: pipes vs electrical runs, columns, keep-outs and racks; runs vs columns and
    keep-outs. Pipes are cylinders of the catalogue OD; busways are 0.2 m x 0.15 m sections."""
    clashes: dict[tuple[str, str], dict] = {}
    runs = electrical_runs(model)
    cols = list(zip([f"COL-{i + 1:02d}" for i in range(len(model.geometry.columns))], column_boxes(model)))
    keepouts = [(f"KO-{i + 1}", box(*k)) for i, k in enumerate(model.geometry.keepouts)]
    racks = [(r.id, box(r.x - r.d / 2, r.y - r.w / 2, r.x + r.d / 2, r.y + r.w / 2)) for r in model.racks]

    def add(a: str, b: str, geom, z: float) -> None:
        if (a, b) not in clashes:
            c = geom.centroid
            clashes[(a, b)] = {"a": a, "b": b, "kind": "solid", "at": [round(c.x, 3), round(c.y, 3), round(z, 3)]}

    for pipe in model.pipes:
        r = PIPE_OD_MM.get(pipe.dn, 219.1) / 2000.0
        for s0, s1 in segments(pipe):
            plan = _plan([(s0.x, s0.y), (s1.x, s1.y)])
            zlo, zhi = min(s0.z, s1.z) - r, max(s0.z, s1.z) + r
            for rid, pts, z_run in runs:
                line = _plan(pts)
                if (zlo < z_run + BUSWAY_HEIGHT_M / 2 and zhi > z_run - BUSWAY_HEIGHT_M / 2
                        and plan.distance(line) < r + BUSWAY_WIDTH_M / 2 - 1e-9):
                    add(pipe.id, rid, plan.intersection(line.buffer(r + BUSWAY_WIDTH_M / 2)), (zlo + zhi) / 2)
            for cid, col in cols:
                if plan.distance(col) < r - 1e-9:
                    add(pipe.id, cid, col, (zlo + zhi) / 2)
            for kid, ko in keepouts:
                if plan.distance(ko) < r - 1e-9:
                    add(pipe.id, kid, ko, (zlo + zhi) / 2)
            if zlo < RACK_HEIGHT_M:
                for rack_id, rb in racks:
                    if plan.distance(rb) < r - 1e-9:
                        add(pipe.id, rack_id, rb, zlo)
    for rid, pts, z_run in runs:
        line = _plan(pts)
        for cid, col in cols:
            if line.distance(col) < BUSWAY_WIDTH_M / 2 - 1e-9:
                add(rid, cid, col, z_run)
        for kid, ko in keepouts:
            if line.distance(ko) < BUSWAY_WIDTH_M / 2 - 1e-9:
                add(rid, kid, ko, z_run)
    return ClashReport(clashes=[clashes[k] for k in sorted(clashes)])
