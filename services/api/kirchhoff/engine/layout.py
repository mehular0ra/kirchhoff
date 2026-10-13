"""Deterministic default rack placement (candidate #1) and plan geometry (spec §9.1)."""
from kirchhoff.contracts import Geometry, Rack

from .scenario import Scenario, limit


def row_index(row_id: str) -> int:
    return int(row_id.removeprefix("R"))


def busway_ids(row_id: str) -> tuple[str, str]:
    n = row_index(row_id)
    return f"A-{n:02d}", f"B-{n:02d}"


def row_of_busway(busway_id: str) -> str:
    return f"R{int(busway_id.split('-')[1])}"


def row_x(scn: Scenario, row_id: str) -> float:
    for row in scn.geometry["rows"]:
        if row["id"] == row_id:
            return float(row["x"])
    raise KeyError(row_id)


def place_racks(scn: Scenario) -> list[Rack]:
    g = scn.geometry
    spec = g["racks"]
    kw, lf = limit(scn, "rack_kw"), limit(scn, "liquid_fraction")
    racks: list[Rack] = []
    for row in g["rows"]:
        feeds = busway_ids(row["id"])
        for k in range(int(spec["per_row"])):
            y = float(spec["y_south"]) + float(spec["w"]) * (k + 0.5)
            racks.append(Rack(id=f"{row['id']}-{k + 1:02d}", row=row["id"], x=float(row["x"]), y=round(y, 3),
                              w=float(spec["w"]), d=float(spec["d"]), kw=kw, liquid_fraction=lf, feeds=feeds))
    return racks


def busway_line(scn: Scenario, busway_id: str) -> tuple[tuple[float, float], tuple[float, float]]:
    """Plan line of a row busway: along the row at x ± offset, from the row's south end to its north end."""
    g = scn.geometry
    side = busway_id[0]
    x = round(row_x(scn, row_of_busway(busway_id)) + float(g["busways"]["offset_a" if side == "A" else "offset_b"]), 3)
    return (x, float(g["racks"]["y_south"])), (x, float(g["racks"]["y_north"]))


def build_geometry(scn: Scenario) -> Geometry:
    g = scn.geometry
    x0, y0, x1, y1 = g["hall"]
    columns = [(float(x), float(y)) for x in g["columns"]["xs"] for y in g["columns"]["ys"]]
    rooms = {k: tuple(float(v) for v in r["rect"]) for k, r in g["rooms"].items()}
    rooms["gallery"] = tuple(float(v) for v in g["gallery"])
    for zid, z in g["zones"].items():
        rooms[f"bay-{zid}"] = tuple(float(v) for v in z["bay"])
    return Geometry(hall=(float(x1 - x0), float(y1 - y0)), columns=columns,
                    keepouts=[tuple(float(v) for v in k["rect"]) for k in g["keepouts"]],
                    rooms=rooms, tiers={k: float(v) for k, v in g["tiers"].items()})
