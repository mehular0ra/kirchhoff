"""Engine-built static bundles for the demo world (spec §13.2). Every number comes from the engine facade; text is
code-authored (P2 ruling R14). Hall A from here is provisional until the golden capture replaces it (Task 14)."""
import importlib
import itertools
from pathlib import Path
from typing import Any, Iterator

from kirchhoff.contracts import (Approval, CrmOverlay, Finding, LedgerEntry, Project, ProjectBundle, PRLine,
                                 PurchaseRequisition, Revision, RunEvent, StepRecord)

from .config import HALL_A_PR_BASE, PUNE_PR_BASE, WorldConfig
from .jsonable import jsonable

POWER_RULES = {"R01", "R02", "R03", "R04", "R04b", "R05", "R06", "R07", "R13"}
COOLING_RULES = {"R08", "R09", "R10", "R11", "R14"}
REVIEWER = "Priya Raman"
REVIEWER_ROLE = "Lead Electrical Engineer (Reviewer)"  # obligations §3.4
AGENT_AUTHOR = "Kirchhoff agents for Arjun Mehta"
MAX_FIX_ITERATIONS = 2
CHIP_WHAT_IFS = [("rack_kw", 200.0), ("rack_kw", 150.0), ("liquid_fraction", 0.9), ("dv_limit_pct", 1.5),
                 ("tx_loading_cap_pct", 35.0)]


def choose_fix(finding: Finding, candidates: list) -> tuple[Any, str, str]:
    """P2 ruling R23, the same criteria the live agents state: Cooling takes the fewest changed pipe segments, then
    cost; Power takes the largest voltage-drop margin per dollar; everything else the cheapest candidate."""
    if finding.rule_id in COOLING_RULES:
        best = min(candidates, key=lambda c: (c.metrics.get("changed_pipes", float("inf")), c.cost_delta, c.id))
        return best, "fewest changed pipe segments, then cost", "cooling"
    if finding.rule_id in POWER_RULES:
        def margin(c) -> float:
            if "dv_pct" not in c.metrics or "dv_limit_pct" not in c.metrics:
                return float("-inf")
            return (c.metrics["dv_limit_pct"] - c.metrics["dv_pct"]) / max(c.cost_delta, 1.0)
        best = sorted(candidates, key=lambda c: (-margin(c), c.cost_delta, c.id))[0]
        return best, "largest voltage-drop margin per dollar", "power"
    return min(candidates, key=lambda c: (c.cost_delta, c.id)), "lowest cost", "procurement"


def pr_id_seq(base: int) -> Iterator[str]:
    return (f"PR-2026-{base + i:04d}" for i in itertools.count())


def prs_by_vendor(lines: list[PRLine], erp, *, project_id: str, revision: str, created_at: float,
                  pr_ids: Iterator[str]) -> list[PurchaseRequisition]:
    """One PR per ERP vendor, vendors in alphabetical order (the live P4 step does the same)."""
    groups: dict[str, list[PRLine]] = {}
    for line in lines:
        groups.setdefault(erp.get(line.material_id).vendor, []).append(line)
    return [PurchaseRequisition(id=next(pr_ids), project_id=project_id, revision=revision, lines=groups[v],
                                status="submitted", created_at=round(created_at + i, 3))
            for i, v in enumerate(sorted(groups))]


def chip_what_ifs(engine, scn, model, erp, ref: str, required: bool = False) -> list:
    fn = getattr(engine, "chip_what_ifs", None)
    if fn is not None:
        return list(fn(scn, model, erp, ref))
    what_if = getattr(engine, "what_if", None)
    if what_if is not None:
        return [what_if(scn, model, p, v, ref, erp) for p, v in CHIP_WHAT_IFS]
    if required:
        raise RuntimeError("engine.what_if is not available yet (WS1 P1 Task 15); chip what-ifs are required")
    return []


def project_record(cfg: WorldConfig, pid: str) -> Project:
    p = cfg.project(pid)
    return Project(id=p.id, name=p.name, client=p.client, asset_pack=p.asset_pack, state=p.state, sample=True,
                   updated_at=cfg.ts(p.days_ago))


def _counts(findings: list[Finding]) -> dict[str, int]:
    return {s: sum(f.status == s for f in findings) for s in ("pass", "fail", "warn", "n/a")}


def _ledger(engine, swaps: list[dict]) -> list[LedgerEntry]:
    did = [LedgerEntry(kind="did", agent="procurement", text=f"{s['from']} replaced by {s['to']} (R15 lead time)")
           for s in swaps if s.get("to")]
    return did + [LedgerEntry(kind="not_checked", agent="checker", text=t) for t in engine.ledger_not_checked()]


def datahall_bundle(engine, scn, erp, *, project: Project, topology: str, signed_at: float, pr_ids: Iterator[str],
                    opportunity_id: str | None = None, what_ifs: bool = False) -> ProjectBundle:
    options = engine.annotate_options(scn, engine.power_options(scn, engine.place_racks(scn)), erp)
    option, model = next((o, m) for o, m in options if o.id == topology)
    model = engine.route(scn, model)
    revs: list[tuple[Any, list[Finding]]] = [(model, engine.check(scn, model, erp))]
    annotated: dict[int, list[Finding]] = {}
    for _ in range(MAX_FIX_ITERATIONS):  # each iteration fixes every failure and makes one revision (P2 R11)
        cur, findings = revs[-1]
        fails = [f for f in findings if f.status == "fail"]
        if not fails:
            break
        marked: dict[str, Finding] = {}
        for f in fails:
            live = {x.id: x for x in engine.check(scn, cur, erp)}.get(f.id)
            if live is None or live.status != "fail":
                continue
            cands = engine.fix_candidates(scn, cur, live, erp)
            if not cands:
                continue
            chosen, criterion, agent = choose_fix(live, cands)
            rejected = next((c for c in sorted(cands, key=lambda c: (c.cost_delta, c.id)) if c.id != chosen.id), None)
            cur = engine.apply_fix(cur, chosen)
            marked[f.id] = f.model_copy(update={
                "fix": {"candidate": chosen.id, "label": chosen.label, "criterion": criterion, "agent": agent,
                        "reason": f"{agent.capitalize()} chose this fix: {criterion}.",
                        "cost_delta": chosen.cost_delta, "deltas": dict(chosen.metrics)},
                "rejected_fix": None if rejected is None else {
                    "candidate": rejected.id, "label": rejected.label, "cost_delta": rejected.cost_delta,
                    "deltas": dict(rejected.metrics)}})
        annotated[len(revs) - 1] = [marked.get(x.id, x) for x in findings]
        revs.append((cur, engine.check(scn, cur, erp)))

    t0 = signed_at - 3600.0 * len(revs)
    revisions, by_rev = [], {}
    for i, (m, findings) in enumerate(revs):
        rid, counts = f"r{i + 1}", _counts(findings)
        status = "signed" if i == len(revs) - 1 and counts["fail"] == 0 else "checked"
        summary = (f"First pass of the {topology} design: {counts['fail']} failing checks." if i == 0
                   else f"After fixes: {counts['pass']} checks pass, {counts['fail']} fail.")
        revisions.append(Revision(id=rid, project_id=project.id, parent=f"r{i}" if i else None, author=AGENT_AUTHOR,
                                  hash=engine.model_hash(m), model=m, summary=summary, check_summary=counts,
                                  status=status, ledger=_ledger(engine, option.swaps), created_at=round(t0 + 3600.0 * i, 3)))
        by_rev[rid] = annotated.get(i, findings)
    signed = revisions[-1]
    if signed.status != "signed":
        raise ValueError(f"{project.id}: {topology} is not checker-clean after {MAX_FIX_ITERATIONS} fix iterations")
    approval = Approval(id=f"appr-{project.id}-1", revision=signed.id, approver_name=REVIEWER, role=REVIEWER_ROLE,
                        decision="approved", comment="Checked the fixes and the assumptions ledger. Approved for procurement.",
                        ts=round(signed_at, 3))
    final = revs[-1][0]
    prs = prs_by_vendor(engine.derive_pr_lines(scn, final, erp), erp, project_id=project.id, revision=signed.id,
                        created_at=signed_at + 120.0, pr_ids=pr_ids)
    crm = (CrmOverlay(opportunity_id=opportunity_id, stage="Design approved", updated_at=round(signed_at + 300.0, 3))
           if opportunity_id else None)
    wifs = chip_what_ifs(engine, scn, final, erp, f"seed:{project.id}@{signed.id}") if what_ifs else []
    return ProjectBundle(project=project.model_copy(update={"updated_at": round(signed_at + 300.0, 3)}),
                         revisions=revisions, findings=by_rev, approvals=[approval], prs=prs, crm=crm, what_ifs=wifs)


def asset_bundle(project: Project, pack: str, result: dict, at: float) -> ProjectBundle:
    """Ruling W18 (P3 R5, P2 R33): tool_call → tool_result {tool, summary + choice} → asset message (choice reason)."""
    tool = {"grid": "evaluate_grid", "solar": "evaluate_solar"}[pack]
    step = "asset.evaluate"
    start, end = round(at - 30.0, 3), round(at, 3)
    summary = jsonable(result)
    reason = f"{summary.get('recommended')} is the engine's recommended option and passes every asset-pack check."
    summary["choice"] = {"option": summary.get("recommended"), "reason": reason, "source": "engine"}
    events = [RunEvent(seq=1, phase="p1", step=step, attempt=1, agent="asset", kind="tool_call",
                       title=f"Asset agent ran {tool}", payload={"tool": tool, "args": {}}, ts=start),
              RunEvent(seq=2, phase="p1", step=step, attempt=1, agent="asset", kind="tool_result",
                       title=f"{tool} finished", payload={"tool": tool, "summary": summary}, ts=end),
              RunEvent(seq=3, phase="p1", step=step, attempt=1, agent="asset", kind="message", title=reason, ts=end)]
    steps = [StepRecord(id=step, phase="p1", status="done", attempt=1, started_at=start, finished_at=end)]
    return ProjectBundle(project=project.model_copy(update={"updated_at": end}), steps=steps, events=events)


def archive_bundle(project: Project, prs: list[PurchaseRequisition]) -> ProjectBundle:
    return ProjectBundle(project=project, prs=sorted(prs, key=lambda p: p.id))


DESIGN_FACADE = ("load_scenario", "place_racks", "power_options", "annotate_options", "route", "check",
                 "fix_candidates", "apply_fix", "derive_pr_lines", "model_hash", "ledger_not_checked")


def engine_bundles(cfg: WorldConfig, engine, scenarios_root: Path, erp,
                   historical_prs: list[PurchaseRequisition]) -> dict[str, ProjectBundle]:
    out = {"vindhya-lv": archive_bundle(project_record(cfg, "vindhya-lv"),
                                        [p for p in historical_prs if p.project_id == "vindhya-lv"])}
    if all(hasattr(engine, name) for name in DESIGN_FACADE):  # skip the designs while WS1's facade is incomplete
        scn = engine.load_scenario("hall_a", scenarios_root)
        out["hall-a"] = datahall_bundle(engine, scn, erp, project=project_record(cfg, "hall-a"), topology="2N",
                                        signed_at=cfg.ts(cfg.project("hall-a").days_ago) - 300.0,
                                        pr_ids=pr_id_seq(HALL_A_PR_BASE), opportunity_id="opp-hall-a", what_ifs=True)
        out["pune-edge-1"] = datahall_bundle(engine, scn, erp, project=project_record(cfg, "pune-edge-1"),
                                             topology="DR", signed_at=cfg.ts(cfg.project("pune-edge-1").days_ago) - 300.0,
                                             pr_ids=pr_id_seq(PUNE_PR_BASE))
    for pid, pack, module, fn in (("grid-132kv", "grid", "kirchhoff.engine.grid", "evaluate_grid"),
                                  ("solar-5mwp", "solar", "kirchhoff.engine.solar", "evaluate_solar")):
        try:
            evaluate = getattr(importlib.import_module(module), fn)
        except (ImportError, AttributeError):
            continue  # WS1 lands the asset packs on Wednesday; rebuild the world once they exist
        rec = project_record(cfg, pid)
        out[pid] = asset_bundle(rec, pack, evaluate(scenarios_root / pack), at=rec.updated_at)
    return out
