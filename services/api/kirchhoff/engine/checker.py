"""The Checker: runs the full rule pack R01–R15 incl. R04b; one Finding per (rule, element) incl. passes."""
from kirchhoff.contracts import DesignModel, Finding, PRLine

from . import rules_admin, rules_cooling, rules_power
from .erp import ErpView
from .findings import RULE_ORDER, Ctx
from .scenario import Scenario

RULE_FUNCS = {
    "R01": rules_power.r01, "R02": rules_power.r02, "R03": rules_power.r03, "R04": rules_power.r04,
    "R04b": rules_power.r04b, "R05": rules_power.r05, "R06": rules_power.r06, "R07": rules_power.r07,
    "R08": rules_cooling.r08, "R09": rules_cooling.r09, "R10": rules_cooling.r10, "R11": rules_cooling.r11,
    "R12": rules_admin.r12, "R13": rules_cooling.r13, "R14": rules_cooling.r14, "R15": rules_admin.r15,
}


def run_rules(scn: Scenario, model: DesignModel, erp: ErpView, pr_lines: list[PRLine] | None = None,
              only: list[str] | None = None) -> list[Finding]:
    ctx = Ctx(scn, model, erp, pr_lines)
    out: list[Finding] = []
    for rid in RULE_ORDER:
        if rid in RULE_FUNCS and (only is None or rid in only):
            out.extend(RULE_FUNCS[rid](ctx))
    return out


def failing(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.status == "fail"]


def summary(findings: list[Finding]) -> dict[str, int]:
    out = {"pass": 0, "fail": 0, "warn": 0, "n/a": 0}
    for f in findings:
        out[f.status] += 1
    return out
