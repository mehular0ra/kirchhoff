"""validate_model (spec §6.3): a facade-level sanity check on a DesignModel. Every facade entry point that
takes a model calls this first, so a malformed or tampered model fails loudly with a clear ValueError instead
of a confusing low-level crash deep inside pandapower or shapely, or — worse — a silently wrong verdict."""
import math

from kirchhoff.contracts import DesignModel

from .scenario import Scenario, cat_item, cat_section

EQUIPMENT_SECTION = {"mv_board": "switchboards", "transformer": "transformers", "lv_board": "switchboards",
                    "critical_board": "switchboards", "sts": "sts", "ups": "ups", "busway": "busways"}
CONNECTION_SECTION = {"busway": "busways", "cable": "cables"}
CONNECTION_KINDS = {"cable", "busway", "internal"}
HEADER_TOL_M = 1e-6


def _point_on_segment(pt: tuple[float, float, float], a: tuple[float, float, float],
                      b: tuple[float, float, float], tol: float) -> bool:
    ax, ay, az = a
    bx, by, bz = b
    px, py, pz = pt
    abx, aby, abz = bx - ax, by - ay, bz - az
    ab_len2 = abx * abx + aby * aby + abz * abz
    if ab_len2 == 0.0:
        t = 0.0
    else:
        apx, apy, apz = px - ax, py - ay, pz - az
        t = max(0.0, min(1.0, (apx * abx + apy * aby + apz * abz) / ab_len2))
    cx, cy, cz = ax + t * abx, ay + t * aby, az + t * abz
    return math.dist((px, py, pz), (cx, cy, cz)) <= tol


def _point_on_polyline(pt: tuple[float, float, float], polyline: list[tuple[float, float, float]],
                       tol: float) -> bool:
    return any(_point_on_segment(pt, a, b, tol) for a, b in zip(polyline, polyline[1:]))


def _resolves(scn: Scenario, catalogue_id: str) -> bool:
    try:
        cat_item(scn, catalogue_id)
        return True
    except KeyError:
        return False


def _dupes(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    dup: list[str] = []
    for i in ids:
        if i in seen and i not in dup:
            dup.append(i)
        seen.add(i)
    return dup


def validate_model(scn: Scenario, model: DesignModel) -> None:
    eq_ids = [e.id for e in model.equipment]
    conn_ids = [c.id for c in model.connections]
    pipe_ids = [p.id for p in model.pipes]
    node_ids = [n.id for n in model.cooling_nodes]
    for label, ids in (("equipment", eq_ids), ("connections", conn_ids), ("pipes", pipe_ids),
                       ("cooling_nodes", node_ids)):
        dup = _dupes(ids)
        if dup:
            raise ValueError(f"duplicate {label} id(s): {', '.join(sorted(dup))}")

    if "MV" not in eq_ids:
        raise ValueError("model has no MV equipment")

    known = set(eq_ids) | set(node_ids)
    for c in model.connections:
        for ref, which in ((c.src, "src"), (c.dst, "dst")):
            if ref not in known:
                raise ValueError(f"connection {c.id} references unknown {which} {ref!r}")
    for r in model.racks:
        for fid in r.feeds:
            if fid not in known:
                raise ValueError(f"rack {r.id} feeds reference unknown busway {fid!r}")

    eq_by_id = {e.id: e for e in model.equipment}
    for c in model.connections:
        if c.kind not in CONNECTION_KINDS:
            raise ValueError(f"connection {c.id} has unknown kind {c.kind!r}")
        dst = eq_by_id.get(c.dst)
        if dst is not None and dst.kind == "busway" and c.kind not in {"busway", "cable"}:
            raise ValueError(f"connection {c.id} feeds a busway but has kind {c.kind!r} "
                             f"(must be 'busway' or 'cable')")

    for e in model.equipment:
        if e.catalogue_id:
            section = EQUIPMENT_SECTION.get(e.kind)
            ids = {i["id"] for i in cat_section(scn, section)} if section else None
            if (ids is not None and e.catalogue_id not in ids) or (ids is None and not _resolves(scn, e.catalogue_id)):
                raise ValueError(f"equipment {e.id} has unknown catalogue id {e.catalogue_id!r}")
        for k, v in e.params.items():
            if k.startswith("brk.") and not k.endswith(".in_a") and not _resolves(scn, str(v)):
                raise ValueError(f"{e.id} breaker {k} has unknown frame id {v!r}")
    for c in model.connections:
        if c.catalogue_id:
            section = CONNECTION_SECTION.get(c.kind)
            ids = {i["id"] for i in cat_section(scn, section)} if section else None
            if (ids is not None and c.catalogue_id not in ids) or (ids is None and not _resolves(scn, c.catalogue_id)):
                raise ValueError(f"connection {c.id} has unknown catalogue id {c.catalogue_id!r}")
        if c.route and len(c.route) < 2:
            raise ValueError(f"connection {c.id} route has fewer than 2 points")
    valid_dns = {int(i["dn"]) for i in cat_section(scn, "pipes")}
    for p in model.pipes:
        if len(p.route) < 2:
            raise ValueError(f"pipe {p.id} route has fewer than 2 points")
        if p.dn not in valid_dns:
            raise ValueError(f"pipe {p.id} has unknown DN {p.dn!r}")

    headers = [p for p in model.pipes if p.kind == "header"]
    for p in model.pipes:
        if p.kind != "branch":
            continue
        first = (p.route[0].x, p.route[0].y, p.route[0].z)
        zone_headers = [h for h in headers if h.zone == p.zone]
        if not any(_point_on_polyline(first, [(pt.x, pt.y, pt.z) for pt in h.route], HEADER_TOL_M)
                  for h in zone_headers):
            raise ValueError(f"branch pipe {p.id} does not take off from a header in zone {p.zone!r}")

    # Terminal pin: every pipe network's two true endpoints (the CDU riser a header starts from, and the
    # row end a branch runs to) are authored geometry, not something a fix or a forged route patch may move.
    # Comparing plan (x, y) only lets mutation M26 legitimately raise BR-R6's end z without tripping this.
    header_geom = scn.geometry.get("pipes", {}).get("headers", {})
    branch_geom = scn.geometry.get("pipes", {}).get("branches", {})
    for p in model.pipes:
        if p.kind == "header" and p.id in header_geom:
            want = tuple(header_geom[p.id][0][:2])
            got = (p.route[0].x, p.route[0].y)
            if got != want:
                raise ValueError(f"{p.id} start is not pinned to the scenario's authored CDU riser "
                                 f"{want} (got {got})")
        elif p.kind == "branch" and p.id in branch_geom:
            want = tuple(branch_geom[p.id][-1][:2])
            got = (p.route[-1].x, p.route[-1].y)
            if got != want:
                raise ValueError(f"{p.id} end is not pinned to the scenario's authored row end "
                                 f"{want} (got {got})")
