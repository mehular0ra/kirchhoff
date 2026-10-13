"""Liquid cooling: CDU sizing per zone (N+1), pipe sizing and hydraulics (spec §8.2, §9.6)."""
import math

from kirchhoff.contracts import CoolingNode, DesignModel, Pipe, Point3, Rack

from . import calc
from .layout import row_x
from .scenario import Scenario, cat_section, limit


def fluid(scn: Scenario) -> tuple[float, float, float]:
    c = scn.catalogue["coolant"]
    return float(c["rho_kg_m3"]), float(c["cp_kj_kgk"]), float(c["mu_pa_s"])


def hydraulics(scn: Scenario) -> dict:
    return scn.catalogue["hydraulics"]


def cdu_spec(scn: Scenario) -> dict:
    return cat_section(scn, "cdus")[0]


def zone_of_row(scn: Scenario, row_id: str) -> str:
    for zid, z in scn.geometry["zones"].items():
        if row_id in z["rows"]:
            return zid
    raise KeyError(row_id)


def zone_liquid_kw(racks: list[Rack], rows: list[str]) -> float:
    return sum(r.kw * r.liquid_fraction for r in racks if r.row in rows)


def rack_required_flow_lps(scn: Scenario, rack: Rack) -> float:
    """max(OEM minimum, flow for ΔT ≤ design ΔT) for one rack."""
    rho, cp, _ = fluid(scn)
    need = calc.vol_flow_lps(rack.kw * rack.liquid_fraction, rho, cp, limit(scn, "delta_t_k"))
    return max(need, float(hydraulics(scn)["oem_min_rack_flow_lpm"]) / 60.0)


def size_cooling(scn: Scenario, racks: list[Rack]) -> list[CoolingNode]:
    """CDUs per zone: N = ceil(zone liquid load / CDU capacity), plus the tender's spare (N+1); then manifolds."""
    cdu = cdu_spec(scn)
    spare = int(limit(scn, "cdu_spare_per_zone"))
    g = scn.geometry
    nodes: list[CoolingNode] = []
    k = 0
    for zid in sorted(g["zones"]):
        z = g["zones"][zid]
        load = zone_liquid_kw(racks, z["rows"])
        n = math.ceil(load / float(cdu["capacity_kw"]) - 1e-9) + spare
        x0, _, x1, _ = z["bay"]
        for i in range(n):
            k += 1
            nodes.append(CoolingNode(id=f"CDU-{k}", kind="cdu", zone=zid, capacity_kw=float(cdu["capacity_kw"]),
                                     x=round(x0 + (i + 0.5) * (x1 - x0) / n, 3), y=float(g["cdu_y"])))
    for zid in sorted(g["zones"]):
        for row in g["zones"][zid]["rows"]:
            nodes.append(CoolingNode(id=f"M-{row}", kind="manifold", zone=zid, x=row_x(scn, row),
                                     y=float(g["manifold_y"])))
    return nodes


def pipe_spec(scn: Scenario, dn: int) -> dict:
    for p in cat_section(scn, "pipes"):
        if int(p["dn"]) == dn:
            return p
    raise KeyError(f"no pipe DN{dn} in catalogue")


def select_dn(scn: Scenario, flow_lps: float) -> int:
    """Smallest catalogue DN whose velocity is within the design velocity (sizing target, not the R10 limit)."""
    target = float(hydraulics(scn)["design_velocity_ms"])
    pipes = sorted(cat_section(scn, "pipes"), key=lambda p: p["dn"])
    for p in pipes:
        if calc.velocity_ms(flow_lps, float(p["id_mm"])) <= target:
            return int(p["dn"])
    return int(pipes[-1]["dn"])


def route_length_m(route: list[Point3]) -> float:
    return sum(math.dist((a.x, a.y, a.z), (b.x, b.y, b.z)) for a, b in zip(route, route[1:]))


def pipe_velocity_ms(scn: Scenario, pipe: Pipe) -> float:
    return calc.velocity_ms(pipe.flow_lps, float(pipe_spec(scn, pipe.dn)["id_mm"]))


def pipe_dp_pa(scn: Scenario, pipe: Pipe) -> float:
    rho, _, mu = fluid(scn)
    return calc.darcy_dp_pa(pipe.flow_lps, float(pipe_spec(scn, pipe.dn)["id_mm"]), route_length_m(pipe.route),
                            rho, mu, float(hydraulics(scn)["roughness_mm"]))


def branch_row(pipe_id: str) -> str:
    return pipe_id.removeprefix("BR-")


def index_dp_kpa(scn: Scenario, model: DesignModel, zone: str) -> tuple[float, str, str]:
    """Index circuit = zone header + worst row branch (supply and return, + fittings allowance) + rack Δp."""
    h = hydraulics(scn)
    headers = [p for p in model.pipes if p.kind == "header" and p.zone == zone]
    branches = [p for p in model.pipes if p.kind == "branch" and p.zone == zone]
    if not headers or not branches:
        return 0.0, "", ""
    header = headers[0]
    worst = max(branches, key=lambda b: (pipe_dp_pa(scn, b), b.id))
    pipe_pa = 2.0 * (1.0 + float(h["fittings_allowance"])) * (pipe_dp_pa(scn, header) + pipe_dp_pa(scn, worst))
    return pipe_pa / 1000.0 + float(h["rack_dp_kpa"]), header.id, worst.id


def build_pipes(scn: Scenario, model: DesignModel,
                routes: dict[str, list[list[float]]] | None = None) -> list[Pipe]:
    """Pipes from the authored polylines in geometry.yaml (or `routes` overrides), sized for the model's racks."""
    g = scn.geometry
    routes = routes or {}
    row_flow: dict[str, float] = {}
    for r in model.racks:
        row_flow[r.row] = row_flow.get(r.row, 0.0) + rack_required_flow_lps(scn, r)
    pipes: list[Pipe] = []
    for pid in sorted(g["pipes"]["headers"]):
        zone = pid.removeprefix("H-")
        flow = sum(row_flow.get(row, 0.0) for row in g["zones"][zone]["rows"])
        pts = routes.get(pid, g["pipes"]["headers"][pid])
        pipes.append(Pipe(id=pid, kind="header", zone=zone, dn=select_dn(scn, flow), tier="pipe_high",
                          route=[Point3(x=p[0], y=p[1], z=p[2]) for p in pts], flow_lps=round(flow, 4)))
    for pid in sorted(g["pipes"]["branches"]):
        row = branch_row(pid)
        flow = row_flow.get(row, 0.0)
        pts = routes.get(pid, g["pipes"]["branches"][pid])
        pipes.append(Pipe(id=pid, kind="branch", zone=zone_of_row(scn, row), dn=select_dn(scn, flow), tier="pipe_low",
                          route=[Point3(x=p[0], y=p[1], z=p[2]) for p in pts], flow_lps=round(flow, 4)))
    return pipes
