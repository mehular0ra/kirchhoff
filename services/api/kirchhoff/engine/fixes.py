"""Fix candidates (spec §6.1): the engine offers only candidates that clear the target finding and create no
new failure (full rule pack re-run per candidate). The owning agent chooses on cost and margin."""
from shapely.geometry import LineString, Point

from kirchhoff.contracts import DesignModel, Finding, Point3
from kirchhoff.contracts.extra import FixCandidate

from .boq import boq_cost
from .checker import run_rules
from .cooling import index_dp_kpa, route_length_m
from .erp import ErpView
from .scenario import Scenario, cat_item, cat_section
from .spatial import electrical_runs, footprint

DROP_MARGIN_M = 0.6


def apply_fix(model: DesignModel, candidate: FixCandidate) -> DesignModel:
    patch = candidate.patch
    if patch["op"] == "set_feeder":
        conns = [c.model_copy(update={"kind": patch["kind"], "catalogue_id": patch["catalogue_id"]})
                 if c.id == patch["feeder"] else c for c in model.connections]
        return model.model_copy(update={"connections": conns})
    if patch["op"] == "set_pipe_routes":
        routes = patch["routes"]
        pipes = [p.model_copy(update={"route": [Point3(x=x, y=y, z=z) for x, y, z in routes[p.id]]})
                 if p.id in routes else p for p in model.pipes]
        return model.model_copy(update={"pipes": pipes})
    raise ValueError(f"unknown fix op {patch['op']!r}")


def _feeder_candidates(scn: Scenario, model: DesignModel, finding: Finding) -> list[FixCandidate]:
    feeder = next(c for c in model.connections if c.id == finding.element_id)
    current = float(cat_item(scn, feeder.catalogue_id)["rating_a"])
    out = []
    for bw in sorted(cat_section(scn, "busways"), key=lambda b: b["rating_a"]):
        if bw["rating_a"] > current:
            out.append(FixCandidate(id=f"{feeder.id}:upsize-{bw['id']}", finding_id=finding.id,
                                    label=f"Upsize {feeder.id} to {bw['rating_a']:,} A busway", cost_delta=0.0,
                                    metrics={}, patch={"op": "set_feeder", "feeder": feeder.id, "kind": "busway",
                                                       "catalogue_id": bw["id"]}))
    for cb in cat_section(scn, "cables"):
        out.append(FixCandidate(id=f"{feeder.id}:cable-{cb['id']}", finding_id=finding.id,
                                label=f"Replace {feeder.id} with a parallel cable feeder ({cb['description']})",
                                cost_delta=0.0, metrics={},
                                patch={"op": "set_feeder", "feeder": feeder.id, "kind": "cable",
                                       "catalogue_id": cb["id"]}))
    return out


def local_drop_route(model: DesignModel, pipe_id: str) -> list[list[float]]:
    """Dip a high pipe down to pipe_low around every electrical run it crosses (± DROP_MARGIN_M along the run)."""
    pipe = next(p for p in model.pipes if p.id == pipe_id)
    tier, low = float(model.geometry.tiers["busway"]), float(model.geometry.tiers["pipe_low"])
    fps = [footprint(pts) for _rid, pts, _z in electrical_runs(model)]
    pts = [[pipe.route[0].x, pipe.route[0].y, pipe.route[0].z]]
    for a, b in zip(pipe.route, pipe.route[1:]):
        if a.z == b.z and a.z > tier and (a.x, a.y) != (b.x, b.y):
            seg = LineString([(a.x, a.y), (b.x, b.y)])
            spans = []
            for fp in fps:
                if seg.intersects(fp):
                    inter = seg.intersection(fp)
                    ds = [seg.project(Point(c)) for g in getattr(inter, "geoms", [inter]) for c in g.coords]
                    spans.append([max(0.0, min(ds) - DROP_MARGIN_M), min(seg.length, max(ds) + DROP_MARGIN_M)])
            spans.sort()
            merged: list[list[float]] = []
            for s in spans:
                if merged and s[0] <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], s[1])
                else:
                    merged.append(s)
            for s0, s1 in merged:
                p0, p1 = seg.interpolate(s0), seg.interpolate(s1)
                pts += [[round(p0.x, 3), round(p0.y, 3), a.z], [round(p0.x, 3), round(p0.y, 3), low],
                        [round(p1.x, 3), round(p1.y, 3), low], [round(p1.x, 3), round(p1.y, 3), a.z]]
        pts.append([b.x, b.y, b.z])
    return [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]


def _pipe_candidates(scn: Scenario, model: DesignModel, finding: Finding) -> list[FixCandidate]:
    pid = finding.element_id
    above = finding.inputs.get("above", "")
    out = []
    if above:
        out.append(FixCandidate(id=f"{pid}:local-drop", finding_id=finding.id,
                                label=f"Drop {pid} to pipe_low where it crosses {above}", cost_delta=0.0, metrics={},
                                patch={"op": "set_pipe_routes", "routes": {pid: local_drop_route(model, pid)}}))
    reroute = scn.geometry.get("reroutes", {}).get(pid)
    if reroute:
        out.append(FixCandidate(id=f"{pid}:reroute", finding_id=finding.id,
                                label=f"Reroute {pid} clear of {above or 'the columns'}", cost_delta=0.0, metrics={},
                                patch={"op": "set_pipe_routes", "routes": {k: v for k, v in reroute.items()}}))
    return out


def _metrics(scn: Scenario, before: DesignModel, after: DesignModel, finding: Finding,
             after_findings: list[Finding]) -> dict[str, float]:
    target = next(f for f in after_findings if f.id == finding.id)
    if finding.rule_id == "R05":
        conn = next(c for c in after.connections if c.id == finding.element_id)
        return {"dv_pct": float(target.value), "dv_limit_pct": float(target.limit),
                "rating_a": float(cat_item(scn, conn.catalogue_id)["rating_a"])}
    if finding.rule_id == "R11":
        pipe = next(p for p in after.pipes if p.id == finding.element_id)
        old = sum(route_length_m(p.route) for p in before.pipes)
        new = sum(route_length_m(p.route) for p in after.pipes)
        changed = sum(1 for a, b in zip(before.pipes, after.pipes) if a.route != b.route)
        return {"crossings": 0.0, "added_pipe_m": round(new - old, 3), "changed_pipes": float(changed),
                "index_dp_kpa": round(index_dp_kpa(scn, after, pipe.zone)[0], 3)}
    return {}


def fix_candidates(scn: Scenario, model: DesignModel, finding: Finding, erp: ErpView) -> list[FixCandidate]:
    if finding.rule_id == "R05":
        raw = _feeder_candidates(scn, model, finding)
    elif finding.rule_id == "R11":
        raw = _pipe_candidates(scn, model, finding)
    else:
        return []
    base_fail = {f.id for f in run_rules(scn, model, erp) if f.status == "fail"}
    base_cost = boq_cost(scn, model)
    out: list[FixCandidate] = []
    upsize_taken = False
    for cand in raw:
        if cand.id.split(":")[1].startswith("upsize") and upsize_taken:
            continue  # offer only the smallest busway upsize that works
        new = apply_fix(model, cand)
        after = run_rules(scn, new, erp)
        after_fail = {f.id for f in after if f.status == "fail"}
        if finding.id in after_fail or after_fail - base_fail:
            continue
        if cand.id.split(":")[1].startswith("upsize"):
            upsize_taken = True
        out.append(cand.model_copy(update={"cost_delta": round(boq_cost(scn, new) - base_cost, 2),
                                           "metrics": _metrics(scn, model, new, finding, after)}))
    return sorted(out, key=lambda c: (c.cost_delta, c.id))
