"""Default routes (candidate #1): feeder bundles along the source room's corridor and authored pipe polylines."""
import math

from kirchhoff.contracts import DesignModel, Point3

from .cooling import build_pipes, size_cooling
from .layout import row_of_busway, row_x
from .scenario import Scenario

Pt = tuple[float, float, float]


def feeder_routes(scn: Scenario, feeders: list[tuple[str, str, str]]) -> dict[str, list[Pt]]:
    """feeders = [(feeder_id, busway_id, source_room)]. Feeders leave their source room's exit, run along that
    room's corridor in a bundle (0.4 m pitch, farthest-going outermost, separately per direction), then turn
    along the row centreline to the row end (spec §9.1)."""
    g = scn.geometry
    z = float(g["tiers"]["busway"])
    groups: dict[tuple[str, str], list[tuple[str, float]]] = {}
    for fid, bid, room in feeders:
        ex = float(g["rooms"][room]["exit"][0])
        xc = row_x(scn, row_of_busway(bid))
        groups.setdefault((room, "west" if xc <= ex else "east"), []).append((fid, xc))
    routes: dict[str, list[Pt]] = {}
    for (room, _direction), items in sorted(groups.items()):
        r = g["rooms"][room]
        ex, ey = (float(v) for v in r["exit"])
        cor = g["corridors"][r["corridor"]]
        items.sort(key=lambda it: (-abs(it[1] - ex), it[0]))
        for k, (fid, xc) in enumerate(items):
            yb = round(float(cor["y_outer"]) + k * float(cor["pitch"]), 3)
            plan = [(ex, ey), (ex, yb), (xc, yb), (xc, float(cor["row_end_y"]))]
            dedup = [plan[0]] + [p for prev, p in zip(plan, plan[1:]) if p != prev]
            routes[fid] = [(x, y, z) for x, y in dedup]
    return routes


def plan_length_m(points: list[Pt]) -> float:
    return sum(math.dist(a[:2], b[:2]) for a, b in zip(points, points[1:]))


def feeder_length_m(scn: Scenario, points: list[Pt]) -> float:
    """Feeder length = horizontal route + 2 × 3.2 m vertical (spec §9.1)."""
    return round(plan_length_m(points) + float(scn.geometry["feeder_vertical_allowance_m"]), 3)


def feeder_specs(model: DesignModel) -> list[tuple[str, str, str]]:
    rooms = {e.id: e.room for e in model.equipment}
    return [(c.id, c.dst, rooms[c.src]) for c in model.connections if c.kind in ("busway", "cable")
            and c.id.startswith("F")]


def route(scn: Scenario, model: DesignModel) -> DesignModel:
    """P3 default routing: feeder polylines (lengths recomputed) and pipes from geometry.yaml. Existing pipes
    are kept, so calling route() on an already-fixed model does not undo pipe fixes."""
    routes = feeder_routes(scn, feeder_specs(model))
    conns = []
    for c in model.connections:
        if c.id in routes:
            pts = routes[c.id]
            c = c.model_copy(update={"route": [Point3(x=x, y=y, z=z) for x, y, z in pts],
                                     "length_m": feeder_length_m(scn, pts)})
        conns.append(c)
    out = model.model_copy(update={"connections": conns})
    if not out.cooling_nodes:
        out = out.model_copy(update={"cooling_nodes": size_cooling(scn, out.racks)})
    if not out.pipes:
        out = out.model_copy(update={"pipes": build_pipes(scn, out)})
    return out
