"""Fix candidates (spec §6.1): the engine offers only candidates that clear the target finding and create no
new failure (full rule pack re-run per candidate). The owning agent chooses on cost and margin."""
import copy

from shapely.geometry import LineString, Point

from kirchhoff.contracts import DesignModel, Finding, Point3
from kirchhoff.contracts.extra import FixCandidate

from .boq import boq_cost
from .checker import run_rules
from .cooling import index_dp_kpa, route_length_m
from .erp import ErpView
from .scenario import Scenario, cat_item, cat_section
from .spatial import electrical_runs, footprint
from .validate import validate_model

DROP_MARGIN_M = 0.6


def apply_fix(model: DesignModel, candidate: FixCandidate) -> DesignModel:
    """Validates the patch before applying it (spec §6.3: nothing an LLM supplies can change a verdict without
    passing through the engine's own checks). apply_fix's signature is frozen (facade), so it cannot take the
    Scenario needed to check a catalogue id against the busway/cable list; that check happens the moment the
    output next passes through a facade entry point (check, route, ...), all of which call validate_model."""
    patch = candidate.patch
    op = patch.get("op")
    if op is None:
        raise ValueError("fix patch has no 'op'")
    if op == "set_feeder":
        fid = patch.get("feeder")
        feeder = next((c for c in model.connections if c.id == fid), None)
        if feeder is None:
            raise ValueError(f"fix patch names an unknown feeder {fid!r}")
        if feeder.kind not in {"busway", "cable"}:
            raise ValueError(f"fix patch targets {fid!r}, which is not a busway or cable feeder "
                             f"(kind {feeder.kind!r})")
        dst = next((e for e in model.equipment if e.id == feeder.dst), None)
        if dst is None or dst.kind != "busway":
            raise ValueError(f"fix patch targets {fid!r}, whose destination is not a busway")
        kind = patch.get("kind")
        if kind not in {"busway", "cable"}:
            raise ValueError(f"fix patch sets feeder {fid!r} to invalid kind {kind!r}")
        catalogue_id = patch.get("catalogue_id")
        if catalogue_id is None:
            raise ValueError(f"fix patch for feeder {fid!r} has no catalogue_id")
        conns = [c.model_copy(update={"kind": kind, "catalogue_id": catalogue_id})
                 if c.id == fid else c for c in model.connections]
        out = model.model_copy(update={"connections": conns})
    elif op == "set_pipe_routes":
        routes = patch.get("routes", {})
        if not isinstance(routes, dict):
            raise ValueError("set_pipe_routes patch 'routes' must be a dict of pipe id -> points")
        pipes_by_id = {p.id: p for p in model.pipes}
        old_ends: dict[str, tuple[tuple, tuple]] = {}
        new_ends: dict[str, tuple[tuple, tuple]] = {}
        for pid, pts in routes.items():
            pipe = pipes_by_id.get(pid)
            if pipe is None:
                raise ValueError(f"fix patch names an unknown pipe {pid!r}")
            if len(pts) < 2:
                raise ValueError(f"fix patch route for {pid} has fewer than 2 points")
            old_ends[pid] = ((pipe.route[0].x, pipe.route[0].y, pipe.route[0].z),
                             (pipe.route[-1].x, pipe.route[-1].y, pipe.route[-1].z))
            new_ends[pid] = (tuple(pts[0]), tuple(pts[-1]))

        def _moved_ok(pid: str, which: int) -> bool:
            """An endpoint may move only as part of a consistent joint: some other pipe touched by the same
            patch shared that exact old point and now shares the exact new point too (e.g. an authored reroute
            that relocates the junction between a header and the branch it feeds)."""
            old_pt, new_pt = old_ends[pid][which], new_ends[pid][which]
            if old_pt == new_pt:
                return True
            return any(old_ends[other][w2] == old_pt and new_ends[other][w2] == new_pt
                      for other in routes if other != pid for w2 in (0, 1))

        for pid in routes:
            for which in (0, 1):
                if not _moved_ok(pid, which):
                    raise ValueError(f"fix patch route for {pid} changes an endpoint")
        pipes = [p.model_copy(update={"route": [Point3(x=x, y=y, z=z) for x, y, z in routes[p.id]]})
                 if p.id in routes else p for p in model.pipes]
        out = model.model_copy(update={"pipes": pipes})
    else:
        raise ValueError(f"unknown fix op {op!r}")
    return out


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
                                patch={"op": "set_pipe_routes", "routes": copy.deepcopy(reroute)}))
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
    """The caller's Finding is never trusted (spec §6.3): the engine's own Checker run is the only source of
    truth for whether `finding.id` is a real, currently-failing element, and every candidate is built from the
    engine's own Finding, never from the caller's `finding.inputs`."""
    validate_model(scn, model)
    all_findings = run_rules(scn, model, erp)
    own = next((f for f in all_findings if f.id == finding.id), None)
    if own is None:
        raise ValueError(f"unknown finding id {finding.id!r}")
    if own.status != "fail":
        return []
    finding = own
    if finding.rule_id == "R05":
        raw = _feeder_candidates(scn, model, finding)
    elif finding.rule_id == "R11":
        raw = _pipe_candidates(scn, model, finding)
    else:
        return []
    base_fail = {f.id for f in all_findings if f.status == "fail"}
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
