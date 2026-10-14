"""Solar asset pack (spec §10, thin): ~5 MWp ground-mount field. String sizing from module Voc at the minimum
site temperature vs the inverter's maximum DC voltage; table layout with Shapely; clear-sky yield from a
deterministic Haurwitz model (no weather API). IEC-based, illustrative, not for construction."""
import math
from pathlib import Path

import numpy as np
import yaml
from shapely.geometry import Polygon, box

from kirchhoff.contracts import ClauseRef, Finding

from .scenario import scenarios_root

RULES = {
    "S01": ("String Voc at minimum temperature", [("IEC 62548", None)], "n·Voc·(1 + β·(T_min − 25)) ≤ V_dc,max"),
    "S02": ("String Vmp at maximum cell temperature", [("IEC 62548", None)], "n·Vmp·(1 + γ·(T_cell,max − 25)) ≥ V_mppt,min"),
    "S03": ("DC/AC ratio", [("Design guideline (illustrative)", None)], "P_dc / P_ac within range"),
    "S04": ("Installed DC capacity", [("Client brief (fictional)", None)], "P_dc ≥ 0.95·target"),
}


def _finding(rule: str, element: str, ok: bool, value: float, limit: float, unit: str, explanation: str) -> Finding:
    title, standards, formula = RULES[rule]
    return Finding(id=f"{rule}:{element}", rule_id=rule, element_id=element, status="pass" if ok else "fail",
                   title=title, clause_refs=[ClauseRef(standard=s, clause=c) for s, c in standards], formula=formula,
                   value=round(value, 4), limit=round(limit, 4), unit=unit, explanation=explanation)


def string_voltages(cfg: dict, n: int) -> tuple[float, float]:
    m, site = cfg["module"], cfg["site"]
    voc_max = n * m["voc_v"] * (1 + m["beta_voc_pct_k"] / 100.0 * (site["tmin_c"] - 25.0))
    vmp_min = n * m["vmp_v"] * (1 + m["gamma_vmp_pct_k"] / 100.0 * (site["tcell_max_c"] - 25.0))
    return voc_max, vmp_min


def layout_tables(cfg: dict, n: int) -> list[tuple[float, float, float, float]]:
    """One string per table, modules in portrait `modules_high` rows; row pitch = slant depth / GCR."""
    m, t = cfg["module"], cfg["table"]
    across = math.ceil(n / int(t["modules_high"]))
    length = across * float(m["width_m"])
    slant = int(t["modules_high"]) * float(m["length_m"])
    depth = slant * math.cos(math.radians(float(t["tilt_deg"])))
    pitch = slant / float(t["gcr"])
    inner = Polygon(cfg["field_polygon"]).buffer(-float(cfg["setback_m"]))
    x0, y0, x1, y1 = inner.bounds
    tables = []
    y = y0
    while y + depth <= y1 + 1e-9:
        x = x0
        while x + length <= x1 + 1e-9:
            b = box(x, y, x + length, y + depth)
            if inner.contains(b):
                tables.append((round(x, 3), round(y, 3), round(x + length, 3), round(y + depth, 3)))
            x += length + float(t["gap_m"])
        y += pitch
    return tables


def clear_sky_kwh_per_kwp(lat_deg: float, tilt_deg: float, albedo: float) -> float:
    """Annual plane-of-array clear-sky irradiation (kWh/m² = kWh/kWp at STC): Haurwitz GHI, 15% diffuse,
    isotropic sky, south-facing fixed tilt, hourly solar time."""
    n = np.arange(1, 366)[:, None]
    hours = np.arange(24)[None, :] + 0.5
    dec = np.radians(23.45) * np.sin(np.radians(360.0 / 365.0 * (284 + n)))
    w = np.radians(15.0 * (hours - 12.0))
    lat, beta = np.radians(lat_deg), np.radians(tilt_deg)
    cosz = np.sin(lat) * np.sin(dec) + np.cos(lat) * np.cos(dec) * np.cos(w)
    up = cosz > 0.01
    ghi = np.where(up, 1098.0 * cosz * np.exp(-0.059 / np.where(up, cosz, 1.0)), 0.0)
    dhi = 0.15 * ghi
    dni = np.where(up, (ghi - dhi) / np.where(up, cosz, 1.0), 0.0)
    cos_inc = np.sin(lat - beta) * np.sin(dec) + np.cos(lat - beta) * np.cos(dec) * np.cos(w)
    poa = dni * np.clip(cos_inc, 0.0, None) + dhi * (1 + np.cos(beta)) / 2 + ghi * albedo * (1 - np.cos(beta)) / 2
    return float(poa.sum() / 1000.0)


def evaluate_option(cfg: dict, n: int, kwh_per_kwp: float) -> dict:
    tables = layout_tables(cfg, n)
    dc_kwp = len(tables) * n * float(cfg["module"]["pmax_w"]) / 1000.0
    inv = cfg["inverter"]
    n_inv = max(1, round(dc_kwp / (float(inv["ac_kw"]) * float(cfg["dc_ac"]["target"]))))
    dc_ac = dc_kwp / (n_inv * float(inv["ac_kw"]))
    voc_max, vmp_min = string_voltages(cfg, n)
    ok_voc = voc_max <= float(inv["vdc_max_v"])
    ok_vmp = vmp_min >= float(inv["mppt_min_v"])
    ok_ratio = float(cfg["dc_ac"]["min"]) <= dc_ac <= float(cfg["dc_ac"]["max"])
    return {"id": f"STR-{n}", "modules_per_string": n, "strings": len(tables), "dc_kwp": round(dc_kwp, 1),
            "inverters": n_inv, "dc_ac": round(dc_ac, 3), "voc_max_v": round(voc_max, 1), "vmp_min_v": round(vmp_min, 1),
            "annual_mwh": round(dc_kwp * kwh_per_kwp * float(cfg["performance_ratio"]) / 1000.0, 1),
            "voc_ok": ok_voc, "vmp_ok": ok_vmp, "dc_ac_ok": ok_ratio, "passes": ok_voc and ok_vmp and ok_ratio,
            "_tables": tables}


def evaluate_solar(scn_dir: Path | None = None) -> dict:
    scn_dir = Path(scn_dir) if scn_dir else scenarios_root() / "solar"
    cfg = yaml.safe_load((scn_dir / "solar.yaml").read_text(encoding="utf-8"))
    site = cfg["site"]
    yield_kwh = clear_sky_kwh_per_kwp(site["lat_deg"], cfg["table"]["tilt_deg"], site["albedo"])
    options = [evaluate_option(cfg, int(n), yield_kwh) for n in cfg["string_options"]]
    passing = [o for o in options if o["passes"]] or options
    rec = sorted(passing, key=lambda o: (-o["dc_kwp"], o["strings"], o["id"]))[0]
    target_kwp = float(cfg["target_mwp"]) * 1000.0
    inv = cfg["inverter"]
    findings = [
        _finding("S01", rec["id"], rec["voc_ok"], rec["voc_max_v"], float(inv["vdc_max_v"]), "V",
                 f"String Voc of {rec['id']} at minimum temperature is {{value}} V against {{limit}} V."),
        _finding("S02", rec["id"], rec["vmp_ok"], rec["vmp_min_v"], float(inv["mppt_min_v"]), "V",
                 f"String Vmp of {rec['id']} at maximum cell temperature is {{value}} V against {{limit}} V."),
        _finding("S03", "INV", rec["dc_ac_ok"], rec["dc_ac"], float(cfg["dc_ac"]["max"]), "",
                 "DC/AC ratio is {value} against a maximum of {limit}."),
        _finding("S04", "FIELD", rec["dc_kwp"] >= 0.95 * target_kwp, rec["dc_kwp"], 0.95 * target_kwp, "kWp",
                 "Installed DC capacity is {value} kWp against {limit} kWp."),
    ]
    tables = rec["_tables"]
    clean = [{k: v for k, v in o.items() if not k.startswith("_")} for o in options]
    geometry = {"polygon": cfg["field_polygon"], "setback_m": cfg["setback_m"], "tables": tables,
                "clear_sky_kwh_per_kwp": round(yield_kwh, 1)}
    return {"options": clean, "recommended": rec["id"], "findings": findings, "geometry": geometry}
