"""Deterministic run policy: plan template, fix owners, Auto option rule (spec §6.1), fix criteria (R23)."""
from kirchhoff.agents.specs import FIX_CRITERIA
from kirchhoff.contracts import TopologyOption

PLAN_TEMPLATE = [
    ("p2.place_racks", "layout", "Place racks (engine default)"),
    ("p2.power_options", "power", "Enumerate power topologies"),
    ("p2.cooling_sizing", "cooling", "Size CDUs and hydraulic zones"),
    ("p2.annotate_options", "procurement", "Check ERP lead times and apply in-stock swaps"),
    ("p2.power_recheck", "power", "Re-check short circuit and loading on swapped options"),
    ("p3.route", "layout", "Route busways and pipes"),
    ("p3.clashes", "layout", "Detect clashes"),
    ("p3.boq", "procurement", "Derive BOQ and draft PR lines"),
    ("p3.check", "checker", "Run the rule pack"),
    ("p3.fix", "power", "Fix loop (at most two iterations)"),
    ("p3.docs", "docs", "Calc report and BOQ"),
    ("p4.create_prs", "procurement", "Create purchase requisitions on approval"),
    ("p4.crm", "system", "Update the CRM opportunity"),
]
OWNER = {"R01": "power", "R02": "power", "R03": "power", "R04": "power", "R04b": "power", "R05": "power",
         "R06": "power", "R07": "power", "R13": "power", "R08": "cooling", "R09": "cooling", "R10": "cooling",
         "R11": "cooling", "R14": "cooling", "R12": "checker", "R15": "procurement"}
RECHECK_RULES = ("R01", "R04", "R04b")
DEFAULT_LEAD_LIMIT_WEEKS = 26
TOPOLOGY_ORDER = {"2N": 0, "DR": 1, "BLOCK": 2}


def lead_limit_weeks(scn) -> int:
    for c in (getattr(scn, "tender", None) or {}).get("clauses", []):
        limits = c.get("limits") or {}
        if "max_lead_time_weeks" in limits:
            return int(limits["max_lead_time_weeks"])
    return DEFAULT_LEAD_LIMIT_WEEKS


def choose_option(options: list[TopologyOption], resolutions: dict[str, str],
                  lead_limit: int) -> TopologyOption | None:
    """Filter by resolved clauses, then the lowest cost with zero SPOF and every lead time within the limit."""
    pool = list(options)
    wanted = {r for r in resolutions.values() if r in TOPOLOGY_ORDER}
    if wanted:
        pool = [o for o in pool if o.id in wanted]
    pool = [o for o in pool if o.spof_count == 0 and o.max_lead_time_weeks <= lead_limit]
    return min(pool, key=lambda o: (o.cost, TOPOLOGY_ORDER.get(o.id, 9)), default=None)


def criterion(owner: str) -> str:
    return FIX_CRITERIA.get(owner, "lowest cost")


def preferred_candidate(owner: str, cands: list):
    if owner == "cooling":
        return min(cands, key=lambda c: (c.metrics.get("changed_pipes", 0.0), c.cost_delta, c.id))
    if owner == "power":
        def margin_per_dollar(c) -> float:
            return (c.metrics.get("dv_limit_pct", 0.0) - c.metrics.get("dv_pct", 0.0)) / max(c.cost_delta, 1.0)
        return min(cands, key=lambda c: (-margin_per_dollar(c), c.cost_delta, c.id))
    return min(cands, key=lambda c: (c.cost_delta, c.id))
