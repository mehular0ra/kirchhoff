"""P2 topology options (spec §9.3): each topology sized with the smallest transformer that passes R01, with
metrics for the option cards; R15 swaps (spec §8.2 r15_swap) and the Power recheck."""
from kirchhoff.contracts import DesignModel, Finding, Rack, TopologyOption

from . import calc
from .boq import boq_cost, boq_quantities, derive_boq
from .checker import run_rules
from .erp import ErpView, effective_lead_weeks
from .findings import EPS
from .redundancy import Study, study
from .scenario import Scenario, cat_item, cat_section, limit
from .shortcircuit import short_circuit
from .topology import TOPOLOGIES, build_model, size_ups_and_breakers


def r01_ok(scn: Scenario, model: DesignModel, st: Study | None = None) -> bool:
    st = st or study(scn, model)
    cap_n, cap_1 = limit(scn, "tx_normal_max_pct"), limit(scn, "tx_n1_max_pct")
    for e in model.equipment:
        if e.kind == "transformer":
            sn = float(e.rating)
            if 100 * st.kva_normal(e.system) / sn > cap_n + EPS or 100 * st.kva_n1(e.system) / sn > cap_1 + EPS:
                return False
    return True


def losses_kw(scn: Scenario, model: DesignModel, st: Study) -> float:
    """Normal-case losses: transformer P0 + Pk·(S/Sn)², UPS P·(1/η − 1), busway and cable I²R."""
    total = 0.0
    eq = {e.id: e for e in model.equipment}
    for e in model.equipment:
        if e.kind == "transformer":
            total += calc.transformer_loss_kw(float(e.params["p0_kw"]), float(e.params["pk_kw"]),
                                              st.kva_normal(e.system), float(e.rating))
        elif e.kind == "ups":
            total += calc.ups_loss_kw(st.normal.ups_kw.get(e.system, 0.0), float(e.params["eta"]))
        elif e.kind == "busway":
            item = cat_item(scn, e.catalogue_id)
            total += calc.run_loss_kw(st.normal.busway_a.get(e.id, 0.0), float(item["r_mohm_m"]),
                                      float(e.params["length_m"]), calc.distributed_loss_factor(int(e.params["taps"])))
    for c in model.connections:
        if c.kind in ("busway", "cable") and c.dst in eq and eq[c.dst].kind == "busway":
            item = cat_item(scn, c.catalogue_id)
            total += calc.run_loss_kw(st.normal.busway_a.get(c.dst, 0.0), float(item["r_mohm_m"]), c.length_m,
                                      1.0, int(item.get("conductors_per_phase", 1)))
    return total


def max_lead_weeks(scn: Scenario, model: DesignModel, erp: ErpView | None) -> int:
    """Without an ERP: the catalogue's nominal lead times. With an ERP: 0 for lines fully in stock."""
    lines = derive_boq(scn, model)
    if erp is None:
        return max(int(cat_item(scn, ln["material_id"])["lead_time_weeks"]) for ln in lines)
    return max(effective_lead_weeks(erp.get(ln["material_id"]), ln["qty"]) for ln in lines)


def option_metrics(scn: Scenario, model: DesignModel, erp: ErpView | None = None,
                   swaps: list[dict] | None = None) -> TopologyOption:
    st = study(scn, model)
    txs = [e for e in model.equipment if e.kind == "transformer"]
    return TopologyOption(
        id=model.topology,
        installed_mva=round(sum(float(e.rating) for e in txs) / 1000.0, 3),
        normal_loading_pct=round(max(100 * st.kva_normal(e.system) / float(e.rating) for e in txs), 2),
        failover_loading_pct=round(max(100 * st.kva_n1(e.system) / float(e.rating) for e in txs), 2),
        cost=round(boq_cost(scn, model), 2), losses_kw=round(losses_kw(scn, model, st), 2),
        max_lead_time_weeks=max_lead_weeks(scn, model, erp), spof_count=len(st.spofs), swaps=swaps or [])


def power_options(scn: Scenario, racks: list[Rack]) -> list[tuple[TopologyOption, DesignModel]]:
    """One entry per topology that passes R01 at its minimum transformer rating (spec §9.6: block is never
    offered on 2.5 MVA because it loads 96% in normal operation)."""
    out = []
    txs = sorted(cat_section(scn, "transformers"), key=lambda t: (t["rating_kva"], t["unit_price"], t["id"]))
    for topo in TOPOLOGIES:
        for tx in txs:
            model = build_model(scn, racks, topo, tx["id"])
            if r01_ok(scn, model):
                out.append((option_metrics(scn, model), model))
                break
    return out


def power_recheck(scn: Scenario, model: DesignModel) -> list[Finding]:
    """Short circuit and R01/R04/R04b on a (swapped) option: the Power agent's p2.power_recheck step."""
    return run_rules(scn, model, erp=None, only=["R01", "R04", "R04b"])


def _category_rating(item: dict) -> float:
    for key in ("rating_kva", "rating_a", "module_kw", "capacity_kw", "frame_a", "dn"):
        if key in item:
            return float(item[key])
    return 0.0


def r15_requirement(scn: Scenario, model: DesignModel, material_id: str) -> float:
    """Transformers: the minimum rating (kVA) satisfying R01 for the computed normal and worst N-1 loads.
    Other lines: the current item's rating."""
    item = cat_item(scn, material_id)
    if "rating_kva" not in item:
        return _category_rating(item)
    st = study(scn, model)
    cap_n, cap_1 = limit(scn, "tx_normal_max_pct") / 100.0, limit(scn, "tx_n1_max_pct") / 100.0
    return max(max(st.kva_normal(e.system) / cap_n, st.kva_n1(e.system) / cap_1)
               for e in model.equipment if e.kind == "transformer" and e.catalogue_id == material_id)


def swap_material(scn: Scenario, model: DesignModel, old_id: str, new_id: str) -> DesignModel:
    if "rating_kva" in cat_item(scn, new_id):
        return build_model(scn, model.racks, model.topology, new_id)  # P2 models are fresh: rebuild exactly
    new_rating = _category_rating(cat_item(scn, new_id))
    eq = [e.model_copy(update={"catalogue_id": new_id, "rating": new_rating}) if e.catalogue_id == old_id else e
          for e in model.equipment]
    conns = [c.model_copy(update={"catalogue_id": new_id}) if c.catalogue_id == old_id else c
             for c in model.connections]
    return size_ups_and_breakers(scn, model.model_copy(update={"equipment": eq, "connections": conns}))


def r15_swap(scn: Scenario, model: DesignModel, material_id: str, erp: ErpView
             ) -> tuple[DesignModel, dict] | None:
    """Spec §8.2: candidates of the same category and voltage, rating ≥ requirement, (stock ≥ qty or lead time
    ≤ limit), sorted by (rating, unit price, id); the first for which R01, R04 and R04b pass after re-running
    short circuit is chosen. Deterministic."""
    current = erp.get(material_id)
    qty = int(round(boq_quantities(scn, model).get(material_id, 0)))
    need = r15_requirement(scn, model, material_id)
    lead_limit = limit(scn, "max_lead_time_weeks")
    cands = []
    for m in erp.search(current.category):
        try:
            cat_item(scn, m.id)
        except KeyError:
            continue  # no engineering data, cannot be checked
        if (m.id != material_id and m.voltage == current.voltage and float(m.rating or 0.0) >= need - EPS
                and (m.stock >= qty or m.lead_time_weeks <= lead_limit)):
            cands.append(m)
    cands.sort(key=lambda m: (float(m.rating or 0.0), m.unit_price, m.id))
    before = short_circuit(scn, model)
    for m in cands:
        new = swap_material(scn, model, material_id, m.id)
        if all(f.status != "fail" for f in power_recheck(scn, new)):
            after = short_circuit(scn, new)
            boards = sorted(k for k in after.ikss_ka if not k.startswith("end:") and k != "MV")
            return new, {"line": current.category, "from": material_id, "to": m.id, "qty": qty, "reason": "R15",
                         "required_rating": round(need, 1), "from_lead_weeks": current.lead_time_weeks,
                         "to_stock": m.stock, "to_lead_weeks": m.lead_time_weeks,
                         "ikss_ka_before": max(before.ikss_ka[b] for b in boards if b in before.ikss_ka),
                         "ikss_ka_after": max(after.ikss_ka[b] for b in boards)}
    return None


def annotate_options(scn: Scenario, options: list[tuple[TopologyOption, DesignModel]], erp: ErpView
                     ) -> list[tuple[TopologyOption, DesignModel]]:
    """Apply r15_swap to every line failing R15, re-run short circuit (inside r15_swap) and recompute metrics
    with ERP lead times; swaps are recorded on the option."""
    out = []
    for _opt, model in options:
        swaps: list[dict] = []
        for f in run_rules(scn, model, erp, only=["R15"]):
            if f.status != "fail":
                continue
            res = r15_swap(scn, model, f.element_id, erp)
            if res is None:
                swaps.append({"line": f.element_id, "from": f.element_id, "to": None,
                              "reason": "R15: no compliant alternative"})
                continue
            model, record = res
            swaps.append(record)
        out.append((option_metrics(scn, model, erp, swaps), model))
    return out
