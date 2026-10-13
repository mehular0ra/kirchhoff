"""Topology builders (spec §9.3): 2N, distributed redundant (4-to-make-3) and block redundant (3 + 1).
All three are generated from the same 12 row busways."""
import math

from kirchhoff.contracts import Connection, DesignModel, Equipment, Rack

from . import calc
from .cooling import cdu_spec, size_cooling
from .layout import build_geometry, busway_ids, busway_line, row_index, row_of_busway
from .redundancy import study
from .routing import feeder_length_m, feeder_routes
from .scenario import Scenario, cat_item, cat_section, limit

TOPOLOGIES = ("2N", "DR", "BLOCK")
DR_PAIRS = [(1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4)]  # rows R1..R6, lexicographic (spec §9.3)


def systems(topo: str) -> list[tuple[str, str]]:
    """(system id, room). The system id is also the LV board id."""
    return {"2N": [("A1", "A"), ("A2", "A"), ("A3", "A"), ("B1", "B"), ("B2", "B"), ("B3", "B")],
            "DR": [("S1", "A"), ("S2", "A"), ("S3", "B"), ("S4", "B")],
            "BLOCK": [("K1", "A"), ("K2", "A"), ("K3", "A"), ("KR", "B")]}[topo]


def busway_sources(topo: str, rows: list[str]) -> dict[str, str]:
    """Row busway id -> source system."""
    out: dict[str, str] = {}
    for row in rows:
        n = row_index(row)
        a, b = busway_ids(row)
        if topo == "2N":
            out[a], out[b] = f"A{(n + 1) // 2}", f"B{(n + 1) // 2}"
        elif topo == "DR":
            lo, hi = DR_PAIRS[n - 1]
            out[a], out[b] = f"S{lo}", f"S{hi}"
        else:
            out[a], out[b] = f"K{(n + 1) // 2}", "KR"
    return out


def feeder_id(busway_id: str) -> str:
    return ("FA-" if busway_id.startswith("A") else "FB-") + busway_id.split("-")[1]


def breaker_frame(scn: Scenario, current_a: float) -> str:
    frames = sorted(cat_section(scn, "breakers"), key=lambda b: b["frame_a"])
    for b in frames:
        if b["frame_a"] >= current_a:
            return b["id"]
    return frames[-1]["id"]


def run_rating_a(scn: Scenario, catalogue_id: str) -> float:
    return float(cat_item(scn, catalogue_id)["rating_a"])


def build_model(scn: Scenario, racks: list[Rack], topo: str, tx_id: str) -> DesignModel:
    """Equipment + connections for one topology with transformer `tx_id`; UPS modules and breakers are sized
    from the N-1 load study. Feeder lengths come from the default routes; `route` points are added in P3."""
    tx = cat_item(scn, tx_id)
    bw = sorted(cat_section(scn, "busways"), key=lambda b: b["rating_a"])[0]
    ups = cat_section(scn, "ups")[0]
    sts = cat_section(scn, "sts")[0]
    rows = sorted({r.row for r in racks}, key=row_index)
    src = busway_sources(topo, rows)
    room_of = dict(systems(topo))
    tiers = scn.geometry["tiers"]
    eq: list[Equipment] = [Equipment(id="MV", kind="mv_board", rating=limit(scn, "mv_kv"), unit="kV",
                                     catalogue_id="MVS-33", params={"sk_mva": limit(scn, "source_sk_mva"),
                                                                    "rx": limit(scn, "source_rx")})]
    conns: list[Connection] = []
    for s, room in systems(topo):
        eq += [
            Equipment(id=f"T-{s}", kind="transformer", rating=float(tx["rating_kva"]), unit="kVA", catalogue_id=tx_id,
                      system=s, room=room, params={"uk_pct": float(tx["uk_pct"]), "p0_kw": float(tx["p0_kw"]),
                                                   "pk_kw": float(tx["pk_kw"])}),
            Equipment(id=s, kind="lv_board", catalogue_id="LVB-415", system=s, room=room,
                      params={"brk.incomer": tx["lv_incomer"]}),
            Equipment(id=f"UPS-{s}", kind="ups", rating=float(ups["module_kw"]) * int(ups["max_modules"]), unit="kW",
                      catalogue_id=ups["id"], system=s, room=room,
                      params={"modules": float(ups["max_modules"]), "eta": float(ups["eta"]),
                              "autonomy_min_full_load": float(ups["autonomy_min_full_load"])}),
            Equipment(id=f"CB-{s}", kind="critical_board", catalogue_id="CRB-415", system=s, room=room, params={}),
        ]
        conns += [Connection(id=f"L-MV-T-{s}", src="MV", dst=f"T-{s}", kind="internal"),
                  Connection(id=f"L-T-{s}", src=f"T-{s}", dst=s, kind="internal"),
                  Connection(id=f"L-{s}-UPS", src=s, dst=f"UPS-{s}", kind="internal"),
                  Connection(id=f"L-UPS-{s}-CB", src=f"UPS-{s}", dst=f"CB-{s}", kind="internal")]
    n_taps = int(scn.geometry["busways"]["taps"])
    feeders: list[tuple[str, str, str]] = []
    feeder_src: dict[str, str] = {}
    for bid in sorted(src):
        s = src[bid]
        (x0, y0), (x1, y1) = busway_line(scn, bid)
        eq.append(Equipment(id=bid, kind="busway", rating=float(bw["rating_a"]), unit="A", catalogue_id=bw["id"],
                            system=s, params={"row": row_of_busway(bid), "side": bid[0], "x0": x0, "y0": y0,
                                              "x1": x1, "y1": y1, "z": float(tiers["busway"]),
                                              "length_m": round(y1 - y0, 3), "taps": float(n_taps)}))
        fid = feeder_id(bid)
        source = f"CB-{s}"
        if topo == "BLOCK" and bid.startswith("B"):
            sts_id = f"STS-{bid.split('-')[1]}"
            eq.append(Equipment(id=sts_id, kind="sts", rating=float(sts["rating_a"]), unit="A",
                                catalogue_id=sts["id"], system="KR", room="B", params={}))
            conns.append(Connection(id=f"L-CB-KR-{sts_id}", src="CB-KR", dst=sts_id, kind="internal"))
            source = sts_id
        feeder_src[fid] = source
        feeders.append((fid, bid, room_of[s]))
    routes = feeder_routes(scn, feeders)
    for fid, bid, _room in feeders:
        conns.append(Connection(id=fid, src=feeder_src[fid], dst=bid, kind="busway", catalogue_id=bw["id"],
                                length_m=feeder_length_m(scn, routes[fid])))
    nodes = size_cooling(scn, racks)
    for zid, z in sorted(scn.geometry["zones"].items()):
        a, b = busway_ids(z["rows"][0])
        sa, sb = src[a], src[b]
        for cdu in [n for n in nodes if n.kind == "cdu" and n.zone == zid]:
            conns += [Connection(id=f"PF-{cdu.id}-1", src=f"CB-{sa}", dst=cdu.id, kind="cable"),
                      Connection(id=f"PF-{cdu.id}-2", src=f"CB-{sb}", dst=cdu.id, kind="cable")]
    n_cdu = sum(1 for n in nodes if n.kind == "cdu")
    loads = {"rack_kw": float(racks[0].kw), "liquid_fraction": float(racks[0].liquid_fraction),
             "aux_mw": limit(scn, "aux_mw"), "pumps_kw": n_cdu * float(cdu_spec(scn)["pump_kw"])}
    model = DesignModel(topology=topo, racks=racks, equipment=eq, connections=conns, cooling_nodes=nodes, pipes=[],
                        geometry=build_geometry(scn), loads=loads)
    return size_ups_and_breakers(scn, model)


def size_ups_and_breakers(scn: Scenario, model: DesignModel) -> DesignModel:
    """UPS modules = ceil(worst N-1 UPS load / module); incomer, UPS-input and feeder breakers from the study."""
    u, pf = limit(scn, "lv_v"), limit(scn, "pf")
    ups_spec = cat_section(scn, "ups")[0]
    st = study(scn, model)
    conns = {c.id: c for c in model.connections}
    new_eq = []
    for e in model.equipment:
        p = dict(e.params)
        if e.kind == "ups":
            modules = min(int(ups_spec["max_modules"]),
                          max(1, math.ceil(st.ups_kw_max(e.system) / float(ups_spec["module_kw"]) - 1e-9)))
            p["modules"] = float(modules)
            e = e.model_copy(update={"rating": modules * float(ups_spec["module_kw"]), "params": p})
        new_eq.append(e)
    ups_rating = {e.system: float(e.rating or 0.0) for e in new_eq if e.kind == "ups"}
    eta = {e.system: float(e.params["eta"]) for e in new_eq if e.kind == "ups"}
    out = []
    for e in new_eq:
        p = dict(e.params)
        if e.kind == "lv_board":
            p["brk.ups_input"] = breaker_frame(scn, calc.design_current_a(ups_rating[e.system] / eta[e.system], u, pf))
        if e.kind in ("critical_board", "sts"):
            if e.kind == "critical_board":
                p["brk.incomer"] = breaker_frame(scn, calc.design_current_a(ups_rating[e.system], u, pf))
            for fid in sorted(c.id for c in conns.values() if c.src == e.id and c.kind in ("busway", "cable")
                              and c.id.startswith("F")):
                feeder = conns[fid]
                ib = st.worst_busway_a(feeder.dst)
                iz = min(run_rating_a(scn, feeder.catalogue_id), next(float(x.rating) for x in new_eq
                                                                        if x.id == feeder.dst))
                frame = breaker_frame(scn, ib)
                p[f"brk.{fid}"] = frame
                p[f"brk.{fid}.in_a"] = min(float(cat_item(scn, frame)["frame_a"]), iz)
        out.append(e.model_copy(update={"params": p}))
    return model.model_copy(update={"equipment": out})
