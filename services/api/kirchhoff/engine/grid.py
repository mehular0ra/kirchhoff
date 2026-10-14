"""Grid asset pack (spec §10, thin): a 132 kV double-circuit line to the campus substation. Three ACSR
conductors compared on N-1 ampacity, voltage regulation and I²R losses; pandapower fault level at the
connection point; mini SLD. IEC-based, illustrative, not for construction."""
import math
import warnings
from pathlib import Path

import yaml

from kirchhoff.contracts import ClauseRef, Finding

from ._locks import WARNINGS_LOCK as _LOCK
from .scenario import scenarios_root

RULES = {
    "G01": ("Conductor ampacity (N-1)", [("IEC TR 61597", None)], "I = S/(√3·U) on one circuit ≤ ampacity"),
    "G02": ("Voltage regulation (N-1)", [("Grid code (illustrative)", None)], "ΔU% = 100·(R·P + X·Q)/U²"),
    "G03": ("132 kV fault level", [("IEC 60909-0", None), ("IEC 62271-100", None)], "I_k″ ≤ switchgear rating"),
    "G04": ("33 kV fault level", [("IEC 60909-0", None), ("IEC 62271-100", None)], "I_k″ ≤ switchgear rating"),
}


def _finding(rule: str, element: str, ok: bool, value: float, limit: float, unit: str, inputs: dict,
             explanation: str) -> Finding:
    title, standards, formula = RULES[rule]
    return Finding(id=f"{rule}:{element}", rule_id=rule, element_id=element, status="pass" if ok else "fail",
                   title=title, clause_refs=[ClauseRef(standard=s, clause=c) for s, c in standards], formula=formula,
                   inputs={k: (round(v, 4) if isinstance(v, float) else v) for k, v in inputs.items()},
                   value=round(value, 4), limit=round(limit, 4), unit=unit, explanation=explanation)


def route_length_km(points: list[list[float]]) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def evaluate_conductor(cfg: dict, cond: dict, length_km: float) -> dict:
    sysc, d = cfg["system"], cfg["design"]
    s_mva, u_kv, pf = float(d["line_capacity_mva"]), float(sysc["un_kv"]), float(sysc["pf"])
    i_n1 = s_mva * 1e6 / (math.sqrt(3) * u_kv * 1e3)  # whole load on one circuit
    i_norm = i_n1 / int(d["circuits"])
    r, x = float(cond["r_ohm_km"]) * length_km, float(cond["x_ohm_km"]) * length_km
    p, q = s_mva * pf, s_mva * math.sqrt(1 - pf * pf)
    reg = 100.0 * (r * p + x * q) * 1e6 / (u_kv * 1e3) ** 2
    losses_kw = int(d["circuits"]) * 3 * i_norm ** 2 * r / 1000.0
    loss_mwh = losses_kw * 8760 * float(d["loss_load_factor"]) / 1000.0
    capex = float(cond["price_usd_km_circuit"]) * length_km * int(d["circuits"])
    lifecycle = capex + int(d["evaluation_years"]) * loss_mwh * 1000 * float(d["energy_price_usd_kwh"])
    ok_amp = i_n1 <= float(cond["ampacity_a"])
    ok_reg = reg <= float(d["regulation_max_pct"])
    return {"id": cond["id"], "name": cond["name"], "ampacity_a": float(cond["ampacity_a"]),
            "n1_current_a": round(i_n1, 1), "regulation_pct": round(reg, 3), "losses_kw": round(losses_kw, 1),
            "annual_loss_mwh": round(loss_mwh, 1), "capex_usd": round(capex, 0), "lifecycle_usd": round(lifecycle, 0),
            "ampacity_ok": ok_amp, "regulation_ok": ok_reg, "passes": ok_amp and ok_reg}


def fault_levels(cfg: dict, cond: dict, length_km: float) -> dict:
    with _LOCK, warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import pandapower as pp
        import pandapower.shortcircuit as sc

        sysc, ss = cfg["system"], cfg["substation"]
        net = pp.create_empty_network(sn_mva=1.0)
        grid = pp.create_bus(net, vn_kv=sysc["un_kv"], name="GRID")
        hv = pp.create_bus(net, vn_kv=sysc["un_kv"], name="SS-132")
        lv = pp.create_bus(net, vn_kv=sysc["lv_kv"], name="SS-33")
        pp.create_ext_grid(net, grid, s_sc_max_mva=sysc["grid_sk_mva"], rx_max=sysc["grid_rx"],
                           s_sc_min_mva=sysc["grid_sk_mva"], rx_min=sysc["grid_rx"])
        for i in range(int(cfg["design"]["circuits"])):
            pp.create_line_from_parameters(net, grid, hv, length_km=length_km, r_ohm_per_km=cond["r_ohm_km"],
                                           x_ohm_per_km=cond["x_ohm_km"], c_nf_per_km=0.0,
                                           max_i_ka=cond["ampacity_a"] / 1000.0, name=f"L-132-{i + 1}")
        for i in range(int(ss["transformers"])):
            sn = float(ss["rating_mva"])
            pp.create_transformer_from_parameters(net, hv, lv, sn_mva=sn, vn_hv_kv=sysc["un_kv"],
                                                  vn_lv_kv=sysc["lv_kv"], vk_percent=ss["uk_pct"],
                                                  vkr_percent=float(ss["pk_kw"]) / (sn * 10.0), pfe_kw=0.0,
                                                  i0_percent=0.0, shift_degree=0, name=f"TX-{i + 1}")
        sc.calc_sc(net, fault="3ph", case="max", ip=True)
        ik = net.res_bus_sc["ikss_ka"]
    return {"ss132_ka": round(float(ik.at[hv]), 3), "ss33_ka": round(float(ik.at[lv]), 3),
            "ss33_mva": round(math.sqrt(3) * float(sysc["lv_kv"]) * float(ik.at[lv]), 1)}


def evaluate_grid(scn_dir: Path | None = None) -> dict:
    scn_dir = Path(scn_dir) if scn_dir else scenarios_root() / "grid"
    cfg = yaml.safe_load((scn_dir / "grid.yaml").read_text(encoding="utf-8"))
    length = route_length_km(cfg["route_km"])
    options = [evaluate_conductor(cfg, c, length) for c in cfg["conductors"]]
    passing = [o for o in options if o["passes"]] or options
    rec = min(passing, key=lambda o: (o["lifecycle_usd"], o["id"]))
    cond = next(c for c in cfg["conductors"] if c["id"] == rec["id"])
    flt = fault_levels(cfg, cond, length)
    d = cfg["design"]
    findings = [
        _finding("G01", "L-132", rec["ampacity_ok"], rec["n1_current_a"], rec["ampacity_a"], "A",
                 {"conductor": rec["id"], "length_km": length},
                 "One circuit of L-132 carries {value} A against an ampacity of {limit} A."),
        _finding("G02", "L-132", rec["regulation_ok"], rec["regulation_pct"], float(d["regulation_max_pct"]), "%",
                 {"conductor": rec["id"]}, "Voltage regulation on one circuit is {value}% against {limit}%."),
        _finding("G03", "SS-132", flt["ss132_ka"] <= float(d["switchgear_132_ka"]), flt["ss132_ka"],
                 float(d["switchgear_132_ka"]), "kA", {}, "Fault level at SS-132 is {value} kA against {limit} kA."),
        _finding("G04", "SS-33", flt["ss33_ka"] <= float(d["switchgear_33_ka"]), flt["ss33_ka"],
                 float(d["switchgear_33_ka"]), "kA", {"ss33_mva": flt["ss33_mva"]},
                 "Fault level at SS-33 is {value} kA against {limit} kA."),
    ]
    geometry = {"route_km": cfg["route_km"], "length_km": round(length, 3),
                "nodes": [{"id": "GRID", "kv": cfg["system"]["un_kv"]}, {"id": "SS-132", "kv": cfg["system"]["un_kv"]},
                          {"id": "SS-33", "kv": cfg["system"]["lv_kv"]}],
                "edges": [{"id": "L-132", "src": "GRID", "dst": "SS-132", "circuits": d["circuits"]},
                          {"id": "TX-SS", "src": "SS-132", "dst": "SS-33",
                           "units": cfg["substation"]["transformers"]}],
                "fault_levels": flt}
    return {"options": options, "recommended": rec["id"], "findings": findings, "geometry": geometry}
