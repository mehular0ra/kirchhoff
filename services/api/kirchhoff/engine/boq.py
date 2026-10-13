"""BOQ and draft PR lines derived from the model before every Checker run (spec §8.2). Quantities: each for
equipment, UPS modules and breakers; metres (rounded up) for busway, cable and pipe runs."""
import math
from collections import defaultdict

from kirchhoff.contracts import DesignModel, PRLine

from .cooling import cdu_spec, route_length_m
from .erp import ErpView, effective_lead_weeks
from .scenario import Scenario, cat_item


def boq_quantities(scn: Scenario, model: DesignModel) -> dict[str, float]:
    qty: dict[str, float] = defaultdict(float)
    for e in model.equipment:
        if e.catalogue_id:
            if e.kind == "ups":
                qty[e.catalogue_id] += float(e.params.get("modules", 1))
            elif e.kind == "busway":
                qty[e.catalogue_id] += float(e.params.get("length_m", 0.0))
            else:
                qty[e.catalogue_id] += 1
        for k, v in e.params.items():
            if k.startswith("brk.") and not k.endswith(".in_a"):
                qty[str(v)] += 1
    for c in model.connections:
        if c.kind in ("busway", "cable") and c.catalogue_id:
            qty[c.catalogue_id] += c.length_m
    n_cdu = sum(1 for n in model.cooling_nodes if n.kind == "cdu")
    if n_cdu:
        qty[cdu_spec(scn)["id"]] += n_cdu
    for p in model.pipes:
        qty[f"PIPE-DN{p.dn}"] += route_length_m(p.route)
    return dict(qty)


def derive_boq(scn: Scenario, model: DesignModel) -> list[dict]:
    """[{material_id, description, qty, unit, unit_price, total}] sorted by material id (catalogue prices)."""
    lines = []
    for mid, q in sorted(boq_quantities(scn, model).items()):
        item = cat_item(scn, mid)
        qty = int(math.ceil(q - 1e-9))
        lines.append({"material_id": mid, "description": item["description"], "qty": qty, "unit": item["unit"],
                      "unit_price": float(item["unit_price"]), "total": qty * float(item["unit_price"])})
    return lines


def boq_cost(scn: Scenario, model: DesignModel) -> float:
    return float(sum(line["total"] for line in derive_boq(scn, model)))


def derive_pr_lines(scn: Scenario, model: DesignModel, erp: ErpView) -> list[PRLine]:
    """One draft PR line per BOQ line, priced from the ERP; lead time 0 when the ERP holds enough stock."""
    out = []
    for line in derive_boq(scn, model):
        m = erp.get(line["material_id"])
        out.append(PRLine(material_id=m.id, description=m.description, qty=line["qty"], unit_price=m.unit_price,
                          lead_time_weeks=effective_lead_weeks(m, line["qty"])))
    return out
