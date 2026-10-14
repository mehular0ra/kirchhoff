"""Electrical rules R01–R07 incl. R04b (spec §8.3)."""
from kirchhoff.contracts import Finding

from . import calc
from .findings import EPS, Ctx, make_finding, status_of
from .scenario import cat_item, limit


def run_rating(ctx: Ctx, catalogue_id: str) -> float:
    return float(cat_item(ctx.scn, catalogue_id)["rating_a"])


def r01(ctx: Ctx) -> list[Finding]:
    cap_n, cap_1 = limit(ctx.scn, "tx_normal_max_pct"), limit(ctx.scn, "tx_n1_max_pct")
    out = []
    for e in sorted((e for e in ctx.model.equipment if e.kind == "transformer"), key=lambda e: e.id):
        sn = float(e.rating)
        n_kva, f_kva = ctx.study.kva_normal(e.system), ctx.study.kva_n1(e.system)
        n_pct, f_pct = 100 * n_kva / sn, 100 * f_kva / sn
        ok = n_pct <= cap_n + EPS and f_pct <= cap_1 + EPS
        value, lim = (f_pct, cap_1) if f_pct / cap_1 > n_pct / cap_n else (n_pct, cap_n)
        out.append(make_finding(ctx.scn, "R01", e.id, status_of(ok), value=value, limit=lim, unit="%",
                                inputs={"normal_kva": n_kva, "n1_kva": f_kva, "rating_kva": sn,
                                        "normal_pct": n_pct, "n1_pct": f_pct, "normal_cap_pct": cap_n,
                                        "n1_cap_pct": cap_1},
                                explanation=f"{e.id} loading reaches {{value}}% against a limit of {{limit}}%."))
    return out


def r02(ctx: Ctx) -> list[Finding]:
    out = []
    for e in sorted((e for e in ctx.model.equipment if e.kind == "busway"), key=lambda e: e.id):
        i = ctx.study.worst_busway_a(e.id)
        out.append(make_finding(ctx.scn, "R02", e.id, status_of(i <= float(e.rating) + EPS), value=i,
                                limit=float(e.rating), unit="A", inputs={"i_failover_a": i, "rating_a": float(e.rating)},
                                explanation=f"{e.id} carries {{value}} A in the worst single failure against a "
                                            f"rating of {{limit}} A."))
    for c in ctx.feeders():
        i, rating = ctx.study.worst_busway_a(c.dst), run_rating(ctx, c.catalogue_id)
        out.append(make_finding(ctx.scn, "R02", c.id, status_of(i <= rating + EPS), value=i, limit=rating, unit="A",
                                inputs={"i_failover_a": i, "rating_a": rating, "catalogue_id": c.catalogue_id},
                                explanation=f"{c.id} carries {{value}} A in the worst single failure against a "
                                            f"rating of {{limit}} A."))
    return out


def r03(ctx: Ctx) -> list[Finding]:
    out = []
    for c in ctx.feeders():
        src = ctx.eq[c.src]
        ib = ctx.study.worst_busway_a(c.dst)
        iz = min(run_rating(ctx, c.catalogue_id), float(ctx.eq[c.dst].rating))
        if f"brk.{c.id}.in_a" not in src.params:
            out.append(make_finding(ctx.scn, "R03", c.id, "fail", inputs={"ib_a": ib, "iz_a": iz},
                                    explanation=f"{c.id} has no feeder breaker."))
            continue
        frame = str(src.params[f"brk.{c.id}"])
        i_n = float(src.params[f"brk.{c.id}.in_a"])
        i2 = float(cat_item(ctx.scn, frame)["i2_factor"]) * i_n
        ok = ib <= i_n + EPS and i_n <= iz + EPS and i2 <= 1.45 * iz + EPS
        out.append(make_finding(ctx.scn, "R03", c.id, status_of(ok), value=i_n, limit=iz, unit="A",
                                inputs={"ib_a": ib, "in_a": i_n, "iz_a": iz, "i2_a": i2, "frame": frame},
                                explanation=f"The breaker on {c.id} is set to {{value}} A; it must lie between the "
                                            f"design current and the run rating of {{limit}} A."))
    return out


def _breakers_at(e) -> list[str]:
    return sorted(str(v) for k, v in e.params.items() if k.startswith("brk.") and not k.endswith(".in_a"))


def r04(ctx: Ctx) -> list[Finding]:
    out = []
    for e in sorted((e for e in ctx.model.equipment if e.kind in ("lv_board", "critical_board", "sts")),
                    key=lambda e: e.id):
        frames = _breakers_at(e)
        if not frames:
            continue
        ik = ctx.sc.ikss_ka[e.id]
        icu = min(float(cat_item(ctx.scn, f)["icu_ka"]) for f in frames)
        out.append(make_finding(ctx.scn, "R04", e.id, status_of(icu >= ik - EPS), value=ik, limit=icu, unit="kA",
                                inputs={"ikss_ka": ik, "ip_ka": ctx.sc.ip_ka[e.id], "icu_ka": icu,
                                        "breakers": ", ".join(frames)},
                                explanation=f"Prospective fault current at {e.id} is {{value}} kA against breaker "
                                            f"Icu of {{limit}} kA."))
    return out


def r04b(ctx: Ctx) -> list[Finding]:
    out = []
    runs = [(c.id, c.src, c.catalogue_id, c.kind) for c in ctx.feeders()]
    runs += [(e.id, f"end:{e.id}", e.catalogue_id, "busway") for e in ctx.model.equipment if e.kind == "busway"]
    for eid, origin, cat_id, kind in sorted(runs):
        if kind != "busway":
            out.append(make_finding(ctx.scn, "R04b", eid, "n/a",
                                    explanation=f"{eid} is a cable run; busway withstand does not apply."))
            continue
        item = cat_item(ctx.scn, cat_id)
        ik, ip = ctx.sc.ikss_ka.get(origin, 0.0), ctx.sc.ip_ka.get(origin, 0.0)
        icw, ipk = float(item["icw_ka"]), float(item["ipk_ka"])
        ok = icw >= ik - EPS and ipk >= ip - EPS
        out.append(make_finding(ctx.scn, "R04b", eid, status_of(ok), value=ik, limit=icw, unit="kA",
                                inputs={"ikss_ka": ik, "ip_ka": ip, "icw_ka": icw, "ipk_ka": ipk, "origin": origin},
                                explanation=f"Prospective fault current at the origin of {eid} is {{value}} kA "
                                            f"against a busway Icw of {{limit}} kA."))
    return out


def feeder_run_length_m(ctx: Ctx, feeder) -> float:
    """The feeder's physical length is judged from its routed geometry whenever one exists; the stored
    `length_m` is used only when there is no route, so a caller cannot shorten the model's billed/plotted
    length to beat R05 while the routed polyline stays long (spec §6.3)."""
    if feeder.route:
        from .routing import feeder_length_m

        return feeder_length_m(ctx.scn, [(p.x, p.y, p.z) for p in feeder.route])
    return feeder.length_m


def feeder_dv_pct(ctx: Ctx, feeder, current_a: float | None = None) -> float:
    """ΔV from the UPS output board to the furthest tap-off: feeder (factor 1) + row busway ((n+1)/(2n))."""
    u, pf = limit(ctx.scn, "lv_v"), limit(ctx.scn, "pf")
    f_item = cat_item(ctx.scn, feeder.catalogue_id)
    busway = ctx.eq[feeder.dst]
    b_item = cat_item(ctx.scn, busway.catalogue_id)
    z_f = calc.z_eff_mohm_m(float(f_item["r_mohm_m"]), float(f_item["x_mohm_m"]), pf,
                            int(f_item.get("conductors_per_phase", 1)))
    z_b = calc.z_eff_mohm_m(float(b_item["r_mohm_m"]), float(b_item["x_mohm_m"]), pf)
    i = ctx.study.worst_busway_a(feeder.dst) if current_a is None else current_a
    sections = [(feeder_run_length_m(ctx, feeder), z_f, 1.0),
                (float(busway.params["length_m"]), z_b, calc.row_factor(int(busway.params["taps"])))]
    return calc.dv_pct(i, sections, u)


def r05(ctx: Ctx) -> list[Finding]:
    lim = limit(ctx.scn, "dv_max_pct")
    out = []
    for c in ctx.feeders():
        dv = feeder_dv_pct(ctx, c)
        out.append(make_finding(ctx.scn, "R05", c.id, status_of(dv <= lim + EPS), value=dv, limit=lim, unit="%",
                                inputs={"i_a": ctx.study.worst_busway_a(c.dst),
                                        "feeder_length_m": feeder_run_length_m(ctx, c),
                                        "busway": c.dst, "catalogue_id": c.catalogue_id, "source": c.src},
                                explanation=f"Voltage drop from the UPS output board to the furthest tap-off via "
                                            f"{c.id} is {{value}}% against a limit of {{limit}}%."))
    return out


def r06(ctx: Ctx) -> list[Finding]:
    if not ctx.study.spofs:
        return [make_finding(ctx.scn, "R06", "HALL", "pass", value=0, limit=0, inputs={"cases": len(ctx.study.cases)},
                             explanation="No single component loss leaves a rack without supply.")]
    out = []
    for comp in ctx.study.spofs:
        case = next(c for c in ctx.study.cases if c.failed == comp)
        out.append(make_finding(ctx.scn, "R06", comp, "fail", value=len(case.unfed), limit=0, unit="racks",
                                inputs={"unfed": ", ".join(case.unfed[:8])},
                                explanation=f"Loss of {comp} leaves racks without any feed."))
    return out


def r07(ctx: Ctx) -> list[Finding]:
    t_min = limit(ctx.scn, "ups_autonomy_min")
    out = []
    for e in sorted((e for e in ctx.model.equipment if e.kind == "ups"), key=lambda e: e.id):
        load = ctx.study.ups_kw_max(e.system)
        cap = float(e.rating)
        autonomy = float(e.params["autonomy_min_full_load"]) * cap / load if load > 0 else float("inf")
        ok = load <= cap + EPS and autonomy >= t_min - EPS
        out.append(make_finding(ctx.scn, "R07", e.id, status_of(ok), value=load, limit=cap, unit="kW",
                                inputs={"load_kw": load, "capacity_kw": cap, "modules": float(e.params["modules"]),
                                        "autonomy_min": min(autonomy, 999.0), "autonomy_limit_min": t_min},
                                explanation=f"{e.id} carries {{value}} kW in the worst single failure against "
                                            f"{{limit}} kW installed."))
    return out
