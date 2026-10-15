"""Cooling and spatial rules R08–R11, R13, R14 (spec §8.3)."""
from kirchhoff.contracts import Finding

from .cooling import cdu_spec, index_dp_kpa, pipe_velocity_ms, rack_required_flow_lps, zone_liquid_kw
from .findings import EPS, Ctx, make_finding, status_of
from .scenario import limit
from .spatial import column_clearance_m, pipe_crossings


def r08(ctx: Ctx) -> list[Finding]:
    spare = int(limit(ctx.scn, "cdu_spare_per_zone"))
    out = []
    for zid in sorted(ctx.scn.geometry["zones"]):
        rows = ctx.scn.geometry["zones"][zid]["rows"]
        caps = sorted((float(n.capacity_kw or 0.0) for n in ctx.model.cooling_nodes
                       if n.kind == "cdu" and n.zone == zid), reverse=True)
        n_cap = sum(caps[spare:])  # the largest `spare` units out of service
        load = zone_liquid_kw(ctx.model.racks, rows)
        out.append(make_finding(ctx.scn, "R08", zid, status_of(load <= n_cap + EPS), value=load, limit=n_cap,
                                unit="kW", inputs={"cdus": float(len(caps)), "spare": float(spare)},
                                explanation=f"Zone {zid} liquid load is {{value}} kW against {{limit}} kW with the "
                                            f"spare CDU out of service."))
    return out


R09_TOL_LPM = 1e-3 * 60.0  # >= cooling.py's 4-dp rounding of flow_lps (0.5e-4 L/s per pipe), as L/min


def r09(ctx: Ctx) -> list[Finding]:
    branches = {p.id.removeprefix("BR-"): p for p in ctx.model.pipes if p.kind == "branch"}
    out = []
    for m in sorted((n for n in ctx.model.cooling_nodes if n.kind == "manifold"), key=lambda n: n.id):
        row = m.id.removeprefix("M-")
        racks = [r for r in ctx.model.racks if r.row == row]
        if row not in branches or not racks:
            out.append(make_finding(ctx.scn, "R09", m.id, "n/a", explanation=f"{m.id} has no routed branch yet."))
            continue
        have = branches[row].flow_lps * 60.0 / len(racks)
        need = max(rack_required_flow_lps(ctx.scn, r) for r in racks) * 60.0
        out.append(make_finding(ctx.scn, "R09", m.id, status_of(have >= need - R09_TOL_LPM), value=have, limit=need,
                                unit="L/min", inputs={"branch": branches[row].id, "racks": float(len(racks))},
                                explanation=f"Rack flow on {m.id} is {{value}} L/min against a requirement of "
                                            f"{{limit}} L/min."))
    return out


def r10(ctx: Ctx) -> list[Finding]:
    lim = limit(ctx.scn, "pipe_velocity_max_ms")
    out = []
    for p in sorted(ctx.model.pipes, key=lambda p: p.id):
        v = pipe_velocity_ms(ctx.scn, p)
        out.append(make_finding(ctx.scn, "R10", p.id, status_of(v <= lim + EPS), value=v, limit=lim, unit="m/s",
                                inputs={"dn": float(p.dn), "flow_lps": p.flow_lps},
                                explanation=f"Velocity in {p.id} is {{value}} m/s against a limit of {{limit}} m/s."))
    return out


def r11(ctx: Ctx) -> list[Finding]:
    c_min = limit(ctx.scn, "column_clearance_mm") / 1000.0
    out = []
    for p in sorted(ctx.model.pipes, key=lambda p: p.id):
        crossings = pipe_crossings(ctx.model, p)
        clearance = column_clearance_m(ctx.model, p)
        if crossings:
            x = crossings[0]
            out.append(make_finding(ctx.scn, "R11", p.id, "fail", value=float(len(crossings)), limit=0.0,
                                    unit="crossings",
                                    inputs={"above": ", ".join(c["run"] for c in crossings), "at_x": x["at"][0],
                                            "at_y": x["at"][1], "at_z": x["at"][2], "clearance_m": clearance},
                                    explanation=f"{p.id} runs above electrical run {x['run']} on a higher tier."))
        else:
            out.append(make_finding(ctx.scn, "R11", p.id, status_of(clearance >= c_min - EPS), value=clearance,
                                    limit=c_min, unit="m", inputs={"above": ""},
                                    explanation=f"{p.id} keeps {{value}} m from the nearest column; minimum "
                                                f"{{limit}} m."))
    return out


def r13(ctx: Ctx) -> list[Finding]:
    out = []
    for cdu in sorted((n for n in ctx.model.cooling_nodes if n.kind == "cdu"), key=lambda n: int(n.id.split("-")[1])):
        sources = [ctx.eq.get(c.src) for c in ctx.model.connections if c.dst == cdu.id]
        ups_systems = sorted({s.system for s in sources if s is not None and s.kind in ("critical_board", "sts")})
        ok = len(ups_systems) >= 2
        out.append(make_finding(ctx.scn, "R13", cdu.id, status_of(ok), value=float(len(ups_systems)), limit=2.0,
                                unit="systems", inputs={"systems": ", ".join(ups_systems)},
                                explanation=f"{cdu.id} pumps have independent UPS-backed supplies from {{value}} "
                                            f"systems; at least {{limit}} systems are required."))
    return out


def r14(ctx: Ctx) -> list[Finding]:
    out = []
    for zid in sorted(ctx.scn.geometry["zones"]):
        dp, header, branch = index_dp_kpa(ctx.scn, ctx.model, zid)
        if not header:
            continue
        head = float(cdu_spec(ctx.scn)["head_kpa"])
        out.append(make_finding(ctx.scn, "R14", header, status_of(dp <= head + EPS), value=dp, limit=head,
                                unit="kPa", inputs={"zone": zid, "branch": branch},
                                explanation=f"The index circuit of {header} needs {{value}} kPa against {{limit}} kPa "
                                            f"available."))
    return out
