"""Rule metadata (spec §8.3, "IEC-based, illustrative values, not for construction") and the Finding builder.
Standards are cited by clause number only. Explanations contain digits only via {value}/{limit} placeholders
and allowlisted ids (spec §6.3)."""
from functools import cached_property

from kirchhoff.contracts import Citation, ClauseRef, DesignModel, Finding, PRLine

from .erp import ErpView
from .scenario import Scenario, clause

EPS = 1e-6
RULE_ORDER = ["R01", "R02", "R03", "R04", "R04b", "R05", "R06", "R07", "R08", "R09", "R10", "R11", "R12", "R13",
              "R14", "R15"]

RULES: dict[str, dict] = {
    "R01": {"title": "Transformer loading", "standards": [("IEC 60076-12", None)], "tender": ["§4.3"],
            "formula": "S = ((P_IT + P_pumps)/η_UPS + P_aux,other)/cosφ; loading = S/S_n (normal and every N-1 case)"},
    "R02": {"title": "Busway/feeder rating at failover current",
            "standards": [("IEC 61439-6", None), ("IEC 60364-5-52", None)], "tender": [],
            "formula": "I_b = Σ P_rack/(√3·U·cosφ) at the worst N-1 case ≤ I_rated"},
    "R03": {"title": "Feeder overload protection", "standards": [("IEC 60364-4-43", "§433.1")], "tender": [],
            "formula": "I_b ≤ I_n ≤ I_z; I_2 = 1.3·I_n ≤ 1.45·I_z"},
    "R04": {"title": "Breaker breaking capacity",
            "standards": [("IEC 60364-4-43", "§434.5.1"), ("IEC 60909-0", None), ("IEC 60947-2", None)],
            "tender": ["§4.4"], "formula": "I_cu ≥ I_k″ (IEC 60909 max case)"},
    "R04b": {"title": "Busway short-circuit withstand", "standards": [("IEC 61439-6", None)], "tender": ["§4.4"],
             "formula": "I_cw ≥ I_k″ and i_pk ≥ i_p at the busway origin"},
    "R05": {"title": "Voltage drop", "standards": [("IEC 60364-5-52", "§525")], "tender": ["§4.6"],
            "formula": "ΔU% = 100·√3·I·Σ L·(R·cosφ + X·sinφ)·k/U; k = 1 (feeder), (n+1)/(2n) (row busway)"},
    "R06": {"title": "Single points of failure",
            "standards": [("ISO/IEC 22237", None), ("EN 50600", None), ("TIA-942", None)], "tender": ["§4.2"],
            "formula": "every rack keeps at least one feed after the loss of any single component"},
    "R07": {"title": "UPS capacity and autonomy", "standards": [], "tender": ["§4.5"],
            "formula": "P_UPS,N-1 ≤ n_modules·P_module; t = t_full·P_rated/P_load ≥ t_min"},
    "R08": {"title": "CDU capacity N+1", "standards": [("ASHRAE TC 9.9", None)], "tender": ["§6.2"],
            "formula": "Σ Q_CDU − spare units ≥ Σ P_rack·f_liquid per zone"},
    "R09": {"title": "Rack coolant flow", "standards": [("OEM rack guide", None)], "tender": ["§6.1"],
            "formula": "q_rack ≥ max(q_OEM,min, Q/(ρ·c_p·ΔT))"},
    "R10": {"title": "Pipe velocity", "standards": [], "tender": ["§6.4"], "formula": "v = 4·V̇/(π·D²) ≤ v_max"},
    "R11": {"title": "Liquid above electrical; column clearance", "standards": [], "tender": ["§6.3.4"],
            "formula": "no pipe segment on a tier above the busway tier over an electrical run; clearance ≥ c_min"},
    "R12": {"title": "SLD, BOQ and PR consistency", "standards": [], "tender": [],
            "formula": "SLD equipment = BOQ lines = PR lines"},
    "R13": {"title": "CDU pump supplies", "standards": [], "tender": ["§6.5"],
            "formula": "each CDU pump fed from ≥ 2 independent UPS-backed systems"},
    "R14": {"title": "Index-circuit pressure drop", "standards": [], "tender": ["§6.2"],
            "formula": "Δp = 2·(1 + a)·(Δp_header + Δp_branch) + Δp_rack ≤ H_CDU (Darcy–Weisbach, Swamee–Jain)"},
    "R15": {"title": "Equipment lead time", "standards": [("ERP data", None)], "tender": ["§2.3"],
            "formula": "stock ≥ quantity, or lead time ≤ tender limit"},
}


def make_finding(scn: Scenario, rule_id: str, element_id: str, status: str, *, value: float | None = None,
                 limit: float | None = None, unit: str | None = None, inputs: dict | None = None,
                 explanation: str = "") -> Finding:
    meta = RULES[rule_id]
    refs = []
    for cid in meta["tender"]:
        c = clause(scn, cid)
        refs.append(Citation(doc_id=scn.tender["doc_id"], page=int(c["page"]), quote=c["quote"], clause=cid))
    return Finding(
        id=f"{rule_id}:{element_id}", rule_id=rule_id, element_id=element_id, status=status, title=meta["title"],
        clause_refs=[ClauseRef(standard=s, clause=c) for s, c in meta["standards"]], tender_refs=refs,
        formula=meta["formula"],
        inputs={k: (round(v, 4) if isinstance(v, float) else v) for k, v in (inputs or {}).items()},
        value=None if value is None else round(float(value), 4),
        limit=None if limit is None else round(float(limit), 4), unit=unit, explanation=explanation)


def status_of(ok: bool) -> str:
    return "pass" if ok else "fail"


class Ctx:
    """Everything one Checker run needs; the load study and short circuit are computed once, lazily."""

    def __init__(self, scn: Scenario, model: DesignModel, erp: ErpView, pr_lines: list[PRLine] | None = None):
        self.scn, self.model, self.erp, self.pr_lines = scn, model, erp, pr_lines
        self.eq = {e.id: e for e in model.equipment}

    @cached_property
    def study(self):
        from .redundancy import study

        return study(self.scn, self.model)

    @cached_property
    def sc(self):
        from .shortcircuit import short_circuit

        return short_circuit(self.scn, self.model)

    def feeders(self):
        return sorted((c for c in self.model.connections if c.kind in ("busway", "cable") and c.dst in self.eq
                       and self.eq[c.dst].kind == "busway"), key=lambda c: c.id)
