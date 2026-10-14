"""What-if (spec §6.4): an engine-only shadow revision, never saved. Loads change; equipment, ratings, routes and
flows stay frozen; all rules re-run. The impact chain lists failing elements in order along
rack → busway → feeder → board → UPS → LV board → transformer and rack → manifold → branch → header → zone → CDU."""
from kirchhoff.contracts import DesignModel, Finding, WhatIfResult

from .checker import run_rules
from .erp import ErpView
from .redundancy import build_graph
from .scenario import Scenario, with_limit

PARAM_BOUNDS = {"rack_kw": (1.0, 400.0), "liquid_fraction": (0.0, 1.0), "dv_limit_pct": (0.1, 10.0),
                "tx_loading_cap_pct": (1.0, 150.0)}
CHIP_WHAT_IFS: list[tuple[str, float]] = [("rack_kw", 200.0), ("rack_kw", 150.0), ("liquid_fraction", 0.9),
                                          ("dv_limit_pct", 1.5), ("tx_loading_cap_pct", 35.0)]


def shadow(scn: Scenario, model: DesignModel, param: str, value: float) -> tuple[Scenario, DesignModel]:
    if param not in PARAM_BOUNDS:
        raise ValueError(f"unknown what-if parameter {param!r}")
    lo, hi = PARAM_BOUNDS[param]
    if not lo <= value <= hi:
        raise ValueError(f"{param} must be within [{lo}, {hi}]")
    if param == "rack_kw":
        racks = [r.model_copy(update={"kw": float(value)}) for r in model.racks]
        return scn, model.model_copy(update={"racks": racks, "loads": {**model.loads, "rack_kw": float(value)}})
    if param == "liquid_fraction":
        racks = [r.model_copy(update={"liquid_fraction": float(value)}) for r in model.racks]
        return scn, model.model_copy(update={"racks": racks,
                                             "loads": {**model.loads, "liquid_fraction": float(value)}})
    if param == "dv_limit_pct":
        return with_limit(scn, "dv_max_pct", float(value)), model
    return with_limit(scn, "tx_normal_max_pct", float(value)), model


def impact_chains(model: DesignModel, findings: list[Finding]) -> list[list[str]]:
    eq = {e.id: e for e in model.equipment}
    failing = {f.element_id for f in findings if f.status == "fail"}
    for f in findings:  # a zone failing R08 means its CDUs are short of capacity
        if f.status == "fail" and f.rule_id == "R08":
            failing |= {n.id for n in model.cooling_nodes if n.kind == "cdu" and n.zone == f.element_id}
    g = build_graph(model)
    chains: list[list[str]] = []

    def keep(path: list[str]) -> None:
        idx = [i for i, el in enumerate(path) if el in failing]
        if idx and idx[-1] >= 1:
            chains.append(path[: idx[-1] + 1])

    for b in sorted(e.id for e in model.equipment if e.kind == "busway"):
        racks = sorted(r.id for r in model.racks if b in r.feeds)
        if not racks:
            continue
        path = [racks[0], b]
        node = b
        while True:
            preds = sorted(g.predecessors(node))
            if not preds or preds[0] == "MV":
                break
            node = preds[0]
            path.append(node)
        keep(path)
    for row in sorted({r.row for r in model.racks}, key=lambda r: int(r[1:])):
        rack = sorted(r.id for r in model.racks if r.row == row)[0]
        branch = next((p for p in model.pipes if p.id == f"BR-{row}"), None)
        zone = branch.zone if branch else next((n.zone for n in model.cooling_nodes if n.id == f"M-{row}"), "")
        cdus = sorted((n.id for n in model.cooling_nodes if n.kind == "cdu" and n.zone == zone),
                      key=lambda c: int(c.split("-")[1]))
        keep([rack, f"M-{row}", f"BR-{row}", f"H-{zone}", zone, *cdus])
    return chains


def what_if(scn: Scenario, model: DesignModel, param: str, value: float, revision_ref: str, erp: ErpView
            ) -> WhatIfResult:
    s2, m2 = shadow(scn, model, param, value)
    findings = run_rules(s2, m2, erp)
    bad = [f for f in findings if f.status in ("fail", "warn")]
    return WhatIfResult(revision_ref=revision_ref, param=param, value=float(value), findings=bad,
                        impact_chain=impact_chains(m2, findings))


def chip_what_ifs(scn: Scenario, model: DesignModel, erp: ErpView, revision_ref: str) -> list[WhatIfResult]:
    """The UI chips, precomputed for static seed bundles (spec §6.4: tour step 5 works with the backend down)."""
    return [what_if(scn, model, p, v, revision_ref, erp) for p, v in CHIP_WHAT_IFS]
