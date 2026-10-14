"""Consistency and procurement rules R12 and R15 (spec §8.3)."""
import math

from kirchhoff.contracts import Finding

from .boq import boq_quantities
from .erp import effective_lead_weeks
from .findings import Ctx, make_finding, status_of
from .scenario import cat_item, limit


def r12(ctx: Ctx) -> list[Finding]:
    """M2: a BOQ material missing from the ERP (get() raising any LookupError, including a sandbox client's own
    subclass) must not crash check(); it is folded into the "unknown" branch instead, so R15's own "not in
    ERP" fail still gets to run."""
    boq = {k: int(math.ceil(v - 1e-9)) for k, v in boq_quantities(ctx.scn, ctx.model).items()}
    unknown = []
    for mid in boq:
        try:
            cat_item(ctx.scn, mid)
        except KeyError:
            unknown.append(mid)
    pr: dict[str, int] = {}
    if ctx.pr_lines is not None:
        for line in ctx.pr_lines:
            pr[line.material_id] = pr.get(line.material_id, 0) + line.qty
    else:
        for mid, qty in boq.items():
            try:
                ctx.erp.get(mid)
            except LookupError:
                unknown.append(mid)
                continue
            pr[mid] = qty
    diff = sorted(set(unknown) | {k for k in set(boq) | set(pr) if boq.get(k, 0) != pr.get(k, 0)})
    expl = "SLD equipment, BOQ lines and PR lines agree." if not diff else \
        f"SLD/BOQ and PR lines differ for {', '.join(diff)}."
    return [make_finding(ctx.scn, "R12", "BOQ", status_of(not diff), value=float(len(diff)), limit=0.0,
                         unit="lines", inputs={"boq_lines": float(len(boq)), "pr_lines": float(len(pr)),
                                               "mismatched": ", ".join(diff)}, explanation=expl)]


def r15(ctx: Ctx) -> list[Finding]:
    lim = limit(ctx.scn, "max_lead_time_weeks")
    out = []
    for mid, q in sorted(boq_quantities(ctx.scn, ctx.model).items()):
        qty = int(math.ceil(q - 1e-9))
        try:
            m = ctx.erp.get(mid)
        except LookupError:
            out.append(make_finding(ctx.scn, "R15", mid, "fail", inputs={"qty": float(qty)},
                                    explanation=f"{mid} is not in the ERP."))
            continue
        lead = effective_lead_weeks(m, qty)
        out.append(make_finding(ctx.scn, "R15", mid, status_of(lead <= lim), value=float(lead), limit=lim,
                                unit="weeks", inputs={"qty": float(qty), "stock": float(m.stock),
                                                      "quoted_lead_weeks": float(m.lead_time_weeks)},
                                explanation=f"{mid} ships in {{value}} weeks against the tender limit of {{limit}} "
                                            f"weeks."))
    return out
