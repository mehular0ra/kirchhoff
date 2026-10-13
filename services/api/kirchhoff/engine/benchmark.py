"""Seeded-fault benchmark (spec §4 metric 3, §16): mutated copies of the checker-clean golden 2N design, each
seeding one fault aimed at a rule. Caught = every expected rule fails; false positive = a rule outside
expect ∪ allow fails. Run: uv run python -m kirchhoff.engine.benchmark"""
import copy
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace

from kirchhoff.contracts import DesignModel, PRLine, Point3

from .checker import failing, run_rules
from .erp import ErpView, YamlErp, default_erp
from .fixes import apply_fix, fix_candidates
from .layout import place_racks
from .options import annotate_options, power_options
from .routing import route
from .scenario import Scenario, cat_item, load_scenario, with_limit


@dataclass
class Bench:
    scn: Scenario
    model: DesignModel
    erp: ErpView
    pr_lines: list[PRLine] | None = None


@dataclass
class Mutation:
    id: str
    target: str
    description: str
    apply: Callable[[Bench], Bench]
    expect: set[str]
    allow: frozenset[str] = frozenset()


def golden_fixed(scn: Scenario, erp: ErpView, topology: str = "2N", max_iter: int = 2) -> DesignModel:
    """The selected option after R15 swaps, default routing and the fix loop (cheapest candidate each time)."""
    options = annotate_options(scn, power_options(scn, place_racks(scn)), erp)
    model = route(scn, next(m for o, m in options if o.id == topology))
    for _ in range(max_iter):
        fails = failing(run_rules(scn, model, erp))
        if not fails:
            break
        for f in fails:
            current = {x.id: x for x in run_rules(scn, model, erp)}[f.id]
            if current.status == "fail":
                cands = fix_candidates(scn, model, current, erp)
                if cands:
                    model = apply_fix(model, cands[0])
    return model


# ---- mutation helpers -------------------------------------------------------------------------------------

def _eq(b: Bench, eid: str, **update) -> Bench:
    eq = [e.model_copy(update=update) if e.id == eid else e for e in b.model.equipment]
    return replace(b, model=b.model.model_copy(update={"equipment": eq}))


def _param(b: Bench, eid: str, key: str, value) -> Bench:
    e = next(x for x in b.model.equipment if x.id == eid)
    return _eq(b, eid, params={**e.params, key: value})


def _conn(b: Bench, cid: str, **update) -> Bench:
    conns = [c.model_copy(update=update) if c.id == cid else c for c in b.model.connections]
    return replace(b, model=b.model.model_copy(update={"connections": conns}))


def _pipe(b: Bench, pid: str, **update) -> Bench:
    pipes = [p.model_copy(update=update) if p.id == pid else p for p in b.model.pipes]
    return replace(b, model=b.model.model_copy(update={"pipes": pipes}))


def _route(b: Bench, pid: str, pts: list[tuple[float, float, float]]) -> Bench:
    return _pipe(b, pid, route=[Point3(x=x, y=y, z=z) for x, y, z in pts])


def _racks(b: Bench, rows: set[str], **update) -> Bench:
    racks = [r.model_copy(update=update) if r.row in rows else r for r in b.model.racks]
    return replace(b, model=b.model.model_copy(update={"racks": racks}))


def _cat(b: Bench, section: str, key: str, value, item_id: str | None = None) -> Bench:
    cat = copy.deepcopy(b.scn.catalogue)
    if isinstance(cat[section], dict):
        cat[section][key] = value
    else:
        for item in cat[section]:
            if item_id is None or item["id"] == item_id:
                item[key] = value
    return replace(b, scn=replace(b.scn, catalogue=cat))


def _limit(b: Bench, key: str, value: float) -> Bench:
    return replace(b, scn=with_limit(b.scn, key, value))


def _erp(b: Bench, mid: str, **update) -> Bench:
    assert isinstance(b.erp, YamlErp), "benchmark ERP mutations need a YamlErp"
    return replace(b, erp=b.erp.with_material(b.erp.get(mid).model_copy(update=update)))


def _loads(b: Bench, **update) -> Bench:
    return replace(b, model=b.model.model_copy(update={"loads": {**b.model.loads, **update}}))


def _swap_tx(b: Bench, eid: str, tx_id: str) -> Bench:
    tx = cat_item(b.scn, tx_id)
    return _eq(b, eid, catalogue_id=tx_id, rating=float(tx["rating_kva"]),
               params={"uk_pct": float(tx["uk_pct"]), "p0_kw": float(tx["p0_kw"]), "pk_kw": float(tx["pk_kw"])})


def _remove_cdu(b: Bench, cdu_id: str) -> Bench:
    nodes = [n for n in b.model.cooling_nodes if n.id != cdu_id]
    conns = [c for c in b.model.connections if c.dst != cdu_id]
    return replace(b, model=b.model.model_copy(update={"cooling_nodes": nodes, "connections": conns}))


def _cdu_capacity(b: Bench, zone: str, kw: float) -> Bench:
    nodes = [n.model_copy(update={"capacity_kw": kw}) if n.kind == "cdu" and n.zone == zone else n
             for n in b.model.cooling_nodes]
    return replace(b, model=b.model.model_copy(update={"cooling_nodes": nodes}))


def _feeds(b: Bench, rack_ids: set[str], feeds: tuple[str, str]) -> Bench:
    racks = [r.model_copy(update={"feeds": feeds}) if r.id in rack_ids else r for r in b.model.racks]
    return replace(b, model=b.model.model_copy(update={"racks": racks}))


def _pr(b: Bench, drop: str | None = None, delta: tuple[str, int] | None = None) -> Bench:
    from .boq import derive_pr_lines

    lines = derive_pr_lines(b.scn, b.model, b.erp)
    if drop:
        lines = [ln for ln in lines if ln.material_id != drop]
    if delta:
        lines = [ln.model_copy(update={"qty": ln.qty + delta[1]}) if ln.material_id == delta[0] else ln
                 for ln in lines]
    return replace(b, pr_lines=lines)


def mutations() -> list[Mutation]:
    r5 = {f"R5-{k:02d}" for k in range(1, 9)}
    return [
        Mutation("M01", "R01", "Normal transformer loading cap lowered to 30%",
                 lambda b: _limit(b, "tx_normal_max_pct", 30.0), {"R01"}),
        Mutation("M02", "R01", "T-A1 swapped to 2.5 MVA and auxiliary load doubled",
                 lambda b: _loads(_swap_tx(b, "T-A1", "TX-2500"), aux_mw=0.6), {"R01", "R15"}),
        Mutation("M03", "R01", "Single-failure loading cap lowered to 70%",
                 lambda b: _limit(b, "tx_n1_max_pct", 70.0), {"R01"}),
        Mutation("M04", "R02", "Row busway A-03 rated 1,250 A", lambda b: _eq(b, "A-03", rating=1250.0),
                 {"R02", "R03"}),
        Mutation("M05", "R02", "Row R6 racks at 140 kW", lambda b: _racks(b, {"R6"}, kw=140.0), {"R02"},
                 frozenset({"R03", "R09"})),
        Mutation("M06", "R03", "FA-02 breaker set below the design current",
                 lambda b: _param(b, "CB-A1", "brk.FA-02.in_a", 1500.0), {"R03"}),
        Mutation("M07", "R03", "FB-04 breaker set above the run rating",
                 lambda b: _param(b, "CB-B2", "brk.FB-04.in_a", 2000.0), {"R03"}),
        Mutation("M08", "R04", "ACB breaking capacity 50 kA", lambda b: _cat(b, "breakers", "icu_ka", 50), {"R04"}),
        Mutation("M09", "R04", "T-B2 impedance 4%", lambda b: _param(b, "T-B2", "uk_pct", 4.0), {"R04", "R04b"}),
        Mutation("M10", "R04b", "Busway Icw 50 kA", lambda b: _cat(b, "busways", "icw_ka", 50), {"R04b"}),
        Mutation("M11", "R04b", "Busway peak withstand 120 kA", lambda b: _cat(b, "busways", "ipk_ka", 120),
                 {"R04b"}),
        Mutation("M12", "R05", "FB-02 routed 60 m longer",
                 lambda b: _conn(b, "FB-02", length_m=next(c.length_m for c in b.model.connections
                                                            if c.id == "FB-02") + 60.0), {"R05"}),
        Mutation("M13", "R05", "Voltage-drop limit 1.0%", lambda b: _limit(b, "dv_max_pct", 1.0), {"R05"}),
        Mutation("M14", "R05", "FA-01 fix reverted to 1,600 A busway",
                 lambda b: _conn(b, "FA-01", kind="busway", catalogue_id="BW-1600"), {"R05"}),
        Mutation("M15", "R06", "Rack R2-03 fed twice from A-02", lambda b: _feeds(b, {"R2-03"}, ("A-02", "A-02")),
                 {"R06"}),
        Mutation("M16", "R06", "Row R5 fed twice from B-05", lambda b: _feeds(b, r5, ("B-05", "B-05")), {"R06"}),
        Mutation("M17", "R07", "UPS-B2 with 4 modules",
                 lambda b: _eq(b, "UPS-B2", rating=2000.0,
                               params={**next(e for e in b.model.equipment if e.id == "UPS-B2").params,
                                       "modules": 4.0}), {"R07"}),
        Mutation("M18", "R07", "UPS-A3 battery 4 min at full load",
                 lambda b: _param(b, "UPS-A3", "autonomy_min_full_load", 4.0), {"R07"}),
        Mutation("M19", "R08", "CDU-6 removed from zone Z2", lambda b: _remove_cdu(b, "CDU-6"), {"R08"}),
        Mutation("M20", "R08", "Zone Z3 CDUs derated to 800 kW", lambda b: _cdu_capacity(b, "Z3", 800.0), {"R08"}),
        Mutation("M21", "R09", "BR-R2 flow reduced by 20%",
                 lambda b: _pipe(b, "BR-R2", flow_lps=next(p.flow_lps for p in b.model.pipes
                                                          if p.id == "BR-R2") * 0.8), {"R09"}),
        Mutation("M22", "R09", "OEM minimum rack flow 200 L/min",
                 lambda b: _cat(b, "hydraulics", "oem_min_rack_flow_lpm", 200.0), {"R09"}),
        Mutation("M23", "R10", "BR-R5 downsized to DN100", lambda b: _pipe(b, "BR-R5", dn=100), {"R10"},
                 frozenset({"R14"})),
        Mutation("M24", "R10", "Velocity limit 1.0 m/s", lambda b: _limit(b, "pipe_velocity_max_ms", 1.0), {"R10"}),
        Mutation("M25", "R11", "H-Z1 routed across FB-02",
                 lambda b: _route(b, "H-Z1", [(8.0, 30.5, 1.2), (8.0, 30.5, 3.8), (23.0, 30.5, 3.8),
                                              (23.0, 21.0, 3.8)]), {"R11"}, frozenset({"R14"})),
        Mutation("M26", "R11", "BR-R6 raised to pipe_high",
                 lambda b: _route(b, "BR-R6", [(43.0, 21.0, 3.8), (46.0, 21.0, 3.8), (46.0, 15.6, 3.8)]), {"R11"},
                 frozenset({"R14"})),
        Mutation("M27", "R11", "BR-R4 routed 0.15 m from a column",
                 lambda b: _route(b, "BR-R4", [(31.0, 24.0, 3.8), (31.0, 24.0, 2.6), (35.65, 24.0, 2.6),
                                               (34.0, 15.6, 2.6)]), {"R11"}, frozenset({"R14"})),
        Mutation("M28", "R12", "PR lines missing the CDU line", lambda b: _pr(b, drop="CDU-1200"), {"R12"}),
        Mutation("M29", "R12", "PR quantity short on BW-1600", lambda b: _pr(b, delta=("BW-1600", -10)), {"R12"}),
        Mutation("M30", "R13", "CDU-2 pumps both fed from CB-A1", lambda b: _conn(b, "PF-CDU-2-2", src="CB-A1"),
                 {"R13"}),
        Mutation("M31", "R13", "CDU-8 pump fed from the non-UPS LV board B3",
                 lambda b: _conn(b, "PF-CDU-8-2", src="B3"), {"R13"}),
        Mutation("M32", "R14", "CDU external head 60 kPa", lambda b: _cat(b, "cdus", "head_kpa", 60.0), {"R14"}),
        Mutation("M33", "R14", "Rack and manifold Δp 145 kPa", lambda b: _cat(b, "hydraulics", "rack_dp_kpa", 145.0),
                 {"R14"}),
        Mutation("M34", "R15", "CDU lead time 40 weeks", lambda b: _erp(b, "CDU-1200", lead_time_weeks=40), {"R15"}),
        Mutation("M35", "R15", "T-A1 swapped back to the 2.5 MVA unit", lambda b: _swap_tx(b, "T-A1", "TX-2500"),
                 {"R15"}),
    ]


def run_benchmark(scn: Scenario | None = None, erp: ErpView | None = None) -> dict:
    scn = scn or load_scenario()
    erp = erp or default_erp()
    model = golden_fixed(scn, erp)
    baseline = sorted({f.rule_id for f in failing(run_rules(scn, model, erp))})
    details = []
    for m in mutations():
        b = m.apply(Bench(scn, model, erp))
        fails = sorted({f.rule_id for f in failing(run_rules(b.scn, b.model, b.erp, b.pr_lines))})
        caught = m.expect <= set(fails)
        unexpected = sorted(set(fails) - m.expect - set(m.allow))
        details.append({"id": m.id, "target": m.target, "description": m.description, "caught": caught,
                        "failing_rules": fails, "unexpected": unexpected})
    n = len(details)
    caught = sum(d["caught"] for d in details)
    return {"mutations": n, "caught": caught, "catch_rate": round(caught / n, 4),
            "false_positive_mutations": sum(1 for d in details if d["unexpected"]),
            "rules_covered": sorted({d["target"] for d in details}), "baseline_failing_rules": baseline,
            "details": details}


if __name__ == "__main__":
    report = run_benchmark()
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    print()
