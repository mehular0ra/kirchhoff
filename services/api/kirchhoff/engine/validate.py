"""validate_model (spec §6.3): a facade-level sanity check on a DesignModel. Every facade entry point that
takes a model calls this first, so a malformed or tampered model fails loudly with a clear ValueError instead
of a confusing low-level crash deep inside pandapower or shapely, or — worse — a silently wrong verdict."""
from kirchhoff.contracts import DesignModel

from .scenario import Scenario, cat_item, cat_section

EQUIPMENT_SECTION = {"mv_board": "switchboards", "transformer": "transformers", "lv_board": "switchboards",
                    "critical_board": "switchboards", "sts": "sts", "ups": "ups", "busway": "busways"}
CONNECTION_SECTION = {"busway": "busways", "cable": "cables"}


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

    known = set(eq_ids) | set(node_ids)
    for c in model.connections:
        for ref, which in ((c.src, "src"), (c.dst, "dst")):
            if ref not in known:
                raise ValueError(f"connection {c.id} references unknown {which} {ref!r}")
    for r in model.racks:
        for fid in r.feeds:
            if fid not in known:
                raise ValueError(f"rack {r.id} feeds reference unknown busway {fid!r}")

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
    for p in model.pipes:
        if len(p.route) < 2:
            raise ValueError(f"pipe {p.id} route has fewer than 2 points")
