"""P2: Layout.place_racks → [Power ∥ Cooling] → Procurement.annotate_options → Power.recheck → OPTION GATE."""
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel

from kirchhoff.agents.specs import COOLING, LAYOUT, POWER, PROCUREMENT
from kirchhoff.contracts import CoolingNode, DesignModel, OpenQuestion, Rack, TopologyOption

from .policy import choose_option, lead_limit_weeks
from .steps import PhaseContext, PhaseOutcome, StepOutput, _n, run_step

S_RESOLVE, S_PLACE, S_POWER = "p2.resolve_plan", "p2.place_racks", "p2.power_options"
S_COOL, S_ANN, S_RECHECK = "p2.cooling_sizing", "p2.annotate_options", "p2.power_recheck"


class OfferReply(BaseModel):
    offer: list[str]
    reason: str = ""


def _pairs(items: list[dict]) -> list[tuple[TopologyOption, DesignModel]]:
    return [(TopologyOption.model_validate(i["option"]), DesignModel.model_validate(i["model"])) for i in items]


def _dump(pairs) -> list[dict]:
    return [{"option": o.model_dump(mode="json"), "model": m.model_dump(mode="json")} for o, m in pairs]


def _rack_ids(racks: list[Rack]) -> list[str]:
    return sorted({x for r in racks for x in (r.id, r.row, *r.feeds)})


def run_p2(ctx: PhaseContext) -> PhaseOutcome:
    run_step(ctx, S_RESOLVE, lambda: _resolve_plan(ctx))
    racks = [Rack.model_validate(r) for r in run_step(ctx, S_PLACE, lambda: _place(ctx))["racks"]]
    with ThreadPoolExecutor(2) as pool:
        f_power = pool.submit(run_step, ctx, S_POWER, lambda: _power(ctx, racks))
        f_cool = pool.submit(run_step, ctx, S_COOL, lambda: _cooling(ctx, racks))
        power, cooling = f_power.result(), f_cool.result()
    ann = run_step(ctx, S_ANN, lambda: _annotate(ctx, power, cooling))
    run_step(ctx, S_RECHECK, lambda: _recheck(ctx, ann))
    return PhaseOutcome(gate="option", run_patch={"options": [i["option"] for i in ann["options"]]})


def _resolve_plan(ctx: PhaseContext) -> StepOutput:
    qs = [OpenQuestion.model_validate(q) for q in ctx.run().get("open_questions", [])]
    out, changed = [], False
    for q in qs:
        if q.resolution is None:
            q = q.model_copy(update={"resolution": q.default_resolution})
            changed = True
            ctx.ledger(S_RESOLVE, "orchestrator", "assumed",
                       f"{q.id} resolved to {q.default_resolution}: the main body governs over the appendix.")
        out.append(q)
    if changed:
        ctx.deps.store.update_doc(ctx.run_path, {"open_questions": [q.model_dump(mode="json") for q in out]})
    return StepOutput(data={"resolutions": {q.id: q.resolution for q in out}})


def _place(ctx: PhaseContext) -> StepOutput:
    scn, box = ctx.scenario(), {}

    def place_racks() -> dict:
        """Place every rack with the engine's deterministic default layout."""
        box["racks"] = ctx.deps.engine.place_racks(scn)
        return {"racks": len(box["racks"]), "rows": sorted({r.row for r in box["racks"]})}

    tool = ctx.tool(S_PLACE, "layout", place_racks)
    res = ctx.agent(LAYOUT, S_PLACE, "Place the racks for the hall, then narrate the result.", tools=[tool])
    if "racks" not in box:
        tool()
    rows = sorted({r.row for r in box["racks"]})
    # R14: code-authored, built only from the engine's own place_racks output -- never the LLM's text.
    template = (f"Layout placed {_n(len(box['racks']), 'rack')} in {_n(len(rows), 'row')} with the engine's "
                f"default pitch.")
    ctx.narrate(S_PLACE, "layout", res.text if res else "", ctx.allowed(extra=_rack_ids(box["racks"])),
                "rack placement", template=template)
    return StepOutput(data={"racks": [r.model_dump(mode="json") for r in box["racks"]]})


def _power(ctx: PhaseContext, racks: list[Rack]) -> StepOutput:
    scn, box = ctx.scenario(), {}

    def enumerate_topologies() -> dict:
        """Enumerate the 2N, distributed-redundant and block-redundant options that pass R01 at minimum rating."""
        box["options"] = ctx.deps.engine.power_options(scn, racks)
        return {"options": [{"id": o.id, "installed_mva": o.installed_mva, "normal_loading_pct": o.normal_loading_pct,
                             "failover_loading_pct": o.failover_loading_pct, "cost": o.cost,
                             "spof_count": o.spof_count} for o, _ in box["options"]]}

    tool = ctx.tool(S_POWER, "power", enumerate_topologies)
    reply = ctx.agent_json(POWER, S_POWER, "Call enumerate_topologies, then decide which options to offer the "
                           'engineer. Reply with JSON {"offer": [option ids], "reason": one sentence}.',
                           OfferReply, tools=[tool])
    if "options" not in box:
        tool()
    ids = [o.id for o, _ in box["options"]]
    offer = [i for i in (reply.offer if reply else []) if i in ids] or ids
    options = [(o, m) for o, m in box["options"] if o.id in offer]
    # R14: code-authored, built only from the engine's power_options output and the offered ids.
    template = (f"Power compared {_n(len(ids), 'topology option')} ({', '.join(sorted(ids))}) and offered "
                f"{len(options)} to the engineer.")
    ctx.narrate(S_POWER, "power", reply.reason if reply else "", ctx.allowed(*[m for _, m in options]),
                "topology options", template=template)
    return StepOutput(data={"options": _dump(options)})


def _cooling(ctx: PhaseContext, racks: list[Rack]) -> StepOutput:
    scn, box = ctx.scenario(), {}

    def size_cdus() -> dict:
        """Size the coolant distribution units per hydraulic zone with N+1 redundancy."""
        box["nodes"] = ctx.deps.engine.size_cooling(scn, racks)
        cdus = [n for n in box["nodes"] if n.kind == "cdu"]
        return {"cdus": len(cdus), "zones": sorted({n.zone for n in cdus})}

    def hydraulic_zones() -> dict:
        """List the hydraulic zones and the CDUs that serve each one."""
        if "nodes" not in box:
            size_cdus()
        zones: dict[str, list[str]] = {}
        for n in box["nodes"]:
            if n.kind == "cdu":
                zones.setdefault(n.zone, []).append(n.id)
        return {"zones": zones}

    t_size, t_zones = ctx.tool(S_COOL, "cooling", size_cdus), ctx.tool(S_COOL, "cooling", hydraulic_zones)
    res = ctx.agent(COOLING, S_COOL, "Size the CDUs and list the hydraulic zones, then narrate.",
                    tools=[t_size, t_zones])
    if "nodes" not in box:
        t_size()
    ids = [x for n in box["nodes"] for x in (n.id, n.zone)] + _rack_ids(racks)
    cdus = [n for n in box["nodes"] if n.kind == "cdu"]
    zones = sorted({n.zone for n in cdus})
    # R14: code-authored, built only from the engine's size_cooling output.
    template = f"Cooling sized {_n(len(cdus), 'CDU', 'CDUs')} across {_n(len(zones), 'zone')}, N+1 per zone."
    ctx.narrate(S_COOL, "cooling", res.text if res else "", ctx.allowed(extra=ids), "CDU sizing", template=template)
    return StepOutput(data={"cooling_nodes": [n.model_dump(mode="json") for n in box["nodes"]]})


def _annotate(ctx: PhaseContext, power: dict, cooling: dict) -> StepOutput:
    scn, erp, box = ctx.scenario(), ctx.erp(), {}
    nodes = [CoolingNode.model_validate(n) for n in cooling["cooling_nodes"]]
    options = [(o, m if m.cooling_nodes else m.model_copy(update={"cooling_nodes": nodes}))
               for o, m in _pairs(power["options"])]  # R20 guard

    def annotate_options() -> dict:
        """Check ERP lead times for every equipment line and apply the engine's in-stock swaps (rule R15)."""
        box["options"] = ctx.deps.engine.annotate_options(scn, options, erp)
        return {"options": [{"id": o.id, "max_lead_time_weeks": o.max_lead_time_weeks, "swaps": o.swaps}
                            for o, _ in box["options"]]}

    tool = ctx.tool(S_ANN, "procurement", annotate_options)
    res = ctx.agent(PROCUREMENT, S_ANN, "Check lead times against the tender limit and apply in-stock swaps, then "
                    "narrate the trade-off.", tools=[tool])
    if "options" not in box:
        tool()
    annotated = box["options"]
    for o, _ in annotated:
        for sw in o.swaps:
            ctx.ledger(S_ANN, "procurement", "did",
                       f"{o.id}: {sw.get('from')} replaced by {sw.get('to')} ({sw.get('reason', 'R15')})")
    rec = choose_option([o for o, _ in annotated], ctx.outputs(S_RESOLVE)["resolutions"], lead_limit_weeks(scn))
    # R14: code-authored, built only from the engine's annotate_options output. The count is distinct
    # catalogue ids across the annotated options' equipment, matching the field R15 and boq_quantities
    # key lead times on (`catalogue_id`, engine/boq.py) -- not equipment instances, which double-counts
    # equipment sharing one catalogue id (e.g. two busways of the same part).
    n_items = len({e.catalogue_id for _, m in annotated for e in m.equipment if e.catalogue_id})
    template = (f"Procurement checked lead times for {_n(n_items, 'catalogue item')} across "
                f"{_n(len(annotated), 'option')}.")
    ctx.narrate(S_ANN, "procurement", res.text if res else "", ctx.allowed(*[m for _, m in annotated]),
                "lead-time check", template=template)
    return StepOutput(data={"options": _dump(annotated), "recommended": rec.id if rec else None})


def _recheck(ctx: PhaseContext, ann: dict) -> StepOutput:
    scn, box = ctx.scenario(), {}
    swapped = [(o, m) for o, m in _pairs(ann["options"]) if o.swaps]

    def recheck_swapped_options() -> dict:
        """Re-run short circuit and rules R01, R04 and R04b on every option whose equipment was swapped."""
        summary = {}
        for o, m in swapped:
            fs = ctx.deps.engine.power_recheck(scn, m)
            summary[o.id] = {"pass": sum(f.status == "pass" for f in fs), "fail": sum(f.status == "fail" for f in fs),
                             "ikss_ka_before": max((float(s["ikss_ka_before"]) for s in o.swaps
                                                    if s.get("ikss_ka_before") is not None), default=None),
                             "ikss_ka_after": max((float(s["ikss_ka_after"]) for s in o.swaps
                                                   if s.get("ikss_ka_after") is not None), default=None)}
        box["summary"] = summary
        return {"options": summary}

    if swapped:
        tool = ctx.tool(S_RECHECK, "power", recheck_swapped_options)
        res = ctx.agent(POWER, S_RECHECK, "Re-check the swapped options with recheck_swapped_options, then "
                        "narrate the fault-level result.", tools=[tool])
        if "summary" not in box:
            tool()
        # R14: code-authored, built only from the swapped option ids the engine's annotate_options produced.
        swap_ids = ", ".join(sorted(o.id for o, _ in swapped))
        template = f"Power re-checked {_n(len(swapped), 'swapped option')} ({swap_ids}) after the R15 swap."
        ctx.narrate(S_RECHECK, "power", res.text if res else "", ctx.allowed(*[m for _, m in swapped]),
                    "fault-level re-check", template=template)
        for oid, s in box["summary"].items():
            if s["fail"]:
                ctx.emit(S_RECHECK, "power", "status", f"{oid} fails a re-checked rule after the swap",
                         payload={"option": oid})
    else:
        box["summary"] = {}
        ctx.emit(S_RECHECK, "power", "status", "No swaps; nothing to re-check")
    ctx.emit(S_RECHECK, "procurement", "artifact", "Options ready",
             payload={"type": "options", "ref": ctx.run_path, "recommended": ann.get("recommended")})
    return StepOutput(data={"recheck": box["summary"]})
