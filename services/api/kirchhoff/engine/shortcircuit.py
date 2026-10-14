"""Prospective short-circuit currents with pandapower calc_sc (IEC 60909, max case, ip=True) at LV boards,
UPS output (critical) boards, STS outputs and busway origins (spec §8.2). UPS static bypass is modelled
closed (worst case), so a critical board sees its LV board's fault level."""
import hashlib
import json
import warnings
from collections import OrderedDict
from dataclasses import dataclass

from kirchhoff.contracts import DesignModel

from ._locks import WARNINGS_LOCK as _LOCK
from .scenario import Scenario, cat_item, limit


@dataclass(frozen=True)
class ScResult:
    ikss_ka: dict[str, float]  # node id -> Ik'' (kA); "end:<busway>" = feeder end / row busway origin
    ip_ka: dict[str, float]  # node id -> peak ip (kA)


_CACHE: "OrderedDict[str, ScResult]" = OrderedDict()
_CACHE_MAX = 32


def _catalogue_fingerprint(scn: Scenario, model: DesignModel) -> list[dict]:
    """Every catalogue entry the calculation actually reads (R/X, conductor count, transformer and MV source
    parameters), keyed by the catalogue id so that two scenarios sharing an id but differing in its underlying
    R/X (or similar) never collide in the cache (I-3)."""
    cat_ids = sorted({e.catalogue_id for e in model.equipment if e.catalogue_id} |
                     {c.catalogue_id for c in model.connections if c.catalogue_id})
    out = []
    for cid in cat_ids:
        try:
            item = cat_item(scn, cid)
        except KeyError:
            continue
        out.append({"id": cid, "r_mohm_m": item.get("r_mohm_m"), "x_mohm_m": item.get("x_mohm_m"),
                    "conductors_per_phase": item.get("conductors_per_phase"), "uk_pct": item.get("uk_pct"),
                    "pk_kw": item.get("pk_kw"), "p0_kw": item.get("p0_kw")})
    return out


def _key(scn: Scenario, model: DesignModel) -> str:
    payload = [e.model_dump(mode="json") for e in model.equipment if e.kind != "busway"]
    payload += [c.model_dump(mode="json", exclude={"route"}) for c in model.connections]
    payload.append({"lv_v": limit(scn, "lv_v"), "mv_kv": limit(scn, "mv_kv"),
                    "catalogue": _catalogue_fingerprint(scn, model)})
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def run_impedance_ohm_km(scn: Scenario, catalogue_id: str) -> tuple[float, float]:
    item = cat_item(scn, catalogue_id)
    n = int(item.get("conductors_per_phase", 1))
    return float(item["r_mohm_m"]) / n, float(item["x_mohm_m"]) / n  # mΩ/m == Ω/km


def short_circuit(scn: Scenario, model: DesignModel) -> ScResult:
    key = _key(scn, model)
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    with _LOCK, warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import pandapower as pp
        import pandapower.shortcircuit as sc

        lv_kv = limit(scn, "lv_v") / 1000.0
        mv_kv = limit(scn, "mv_kv")
        eq = {e.id: e for e in model.equipment}
        net = pp.create_empty_network(sn_mva=1.0)
        bus: dict[str, int] = {}
        mv = eq["MV"]
        bus["MV"] = pp.create_bus(net, vn_kv=mv_kv, name="MV")
        pp.create_ext_grid(net, bus["MV"], s_sc_max_mva=float(mv.params["sk_mva"]), rx_max=float(mv.params["rx"]),
                           s_sc_min_mva=float(mv.params["sk_mva"]), rx_min=float(mv.params["rx"]))
        for e in model.equipment:
            if e.kind in ("lv_board", "critical_board", "sts"):
                bus[e.id] = pp.create_bus(net, vn_kv=lv_kv, name=e.id)
        for c in model.connections:
            if c.kind != "internal":
                continue
            src, dst = eq.get(c.src), eq.get(c.dst)
            if src is None or dst is None:
                continue
            if src.kind == "transformer" and dst.kind == "lv_board":
                sn = float(src.rating) / 1000.0
                pp.create_transformer_from_parameters(
                    net, bus["MV"], bus[dst.id], sn_mva=sn, vn_hv_kv=mv_kv, vn_lv_kv=lv_kv,
                    vk_percent=float(src.params["uk_pct"]), vkr_percent=float(src.params["pk_kw"]) / (sn * 10.0),
                    pfe_kw=float(src.params["p0_kw"]), i0_percent=0.5, shift_degree=330, vector_group="Dyn",
                    name=src.id)
        for e in model.equipment:  # UPS bypass: LV board -> critical board (closed bus-bus switch)
            if e.kind == "critical_board":
                pp.create_switch(net, bus[e.system], bus[e.id], et="b", closed=True)
        for c in model.connections:  # critical board -> STS
            if c.kind == "internal" and c.dst in eq and eq[c.dst].kind == "sts":
                pp.create_switch(net, bus[c.src], bus[c.dst], et="b", closed=True)
        for c in model.connections:  # feeders: busway or parallel cable runs
            if c.kind in ("busway", "cable") and c.src in bus and c.dst in eq:
                end = pp.create_bus(net, vn_kv=lv_kv, name=f"end:{c.dst}")
                bus[f"end:{c.dst}"] = end
                r, x = run_impedance_ohm_km(scn, c.catalogue_id)
                pp.create_line_from_parameters(net, bus[c.src], end, length_km=max(c.length_m, 0.1) / 1000.0,
                                               r_ohm_per_km=r, x_ohm_per_km=x, c_nf_per_km=0.0, max_i_ka=10.0,
                                               name=c.id)
        sc.calc_sc(net, fault="3ph", case="max", ip=True, lv_tol_percent=10)
        res = net.res_bus_sc
        names = {idx: name for name, idx in bus.items()}
        ikss = {names[i]: round(float(res.at[i, "ikss_ka"]), 3) for i in res.index if i in names}
        ip = {names[i]: round(float(res.at[i, "ip_ka"]), 3) for i in res.index if i in names}
    result = ScResult(ikss, ip)
    with _LOCK:
        _CACHE[key] = result
        if len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
    return result
