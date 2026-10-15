"""P3: select → route → clashes → BOQ → Checker → fix loop (≤ 2, one revision each) → Docs → REVIEW GATE."""
import logging
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel

from kirchhoff.agents.docs_export import SECTIONS, StubExporter
from kirchhoff.agents.specs import COOLING, DOCS, LAYOUT, POWER
from kirchhoff.agents.trust import sanitize
from kirchhoff.contracts import DesignBrief, DesignModel, Finding, LedgerEntry, PRLine, Revision, TopologyOption

from .policy import OWNER, choose_option, criterion, lead_limit_weeks, preferred_candidate
from .revisions import build_revision, diff_elements, load_revision_model, run_revisions, with_citation_boxes
from .steps import AGENT_LABEL, ParkAtGate, PhaseContext, PhaseOutcome, StepOutput, _n, run_step

log = logging.getLogger("kirchhoff")
MAX_FIX_ITERATIONS = 2
EXPORT_FAILED = "Calc report and BOQ exports could not be published; the checked revision is unaffected."
S_SELECT, S_ROUTE, S_CLASH, S_BOQ, S_DOCS = "p3.select_option", "p3.route", "p3.clashes", "p3.boq", "p3.docs"


class FixChoice(BaseModel):
    candidate_id: str
    reason: str = ""


class DocsReply(BaseModel):
    order: list[str] = []
    summary: str = ""


def run_p3(ctx: PhaseContext) -> PhaseOutcome:
    sel = run_step(ctx, S_SELECT, lambda: _select(ctx))["option_id"]
    model = DesignModel.model_validate(run_step(ctx, S_ROUTE, lambda: _route(ctx, sel))["model"])
    run_step(ctx, S_CLASH, lambda: _clashes(ctx, model))
    lines = run_step(ctx, S_BOQ, lambda: _boq(ctx, model))["pr_lines"]
    chk = run_step(ctx, "p3.check.1", lambda: _check(ctx, 1, None, model, None, lines))
    n, iterations, stop_reason = 1, 0, None
    while chk["fail_ids"] and n <= MAX_FIX_ITERATIONS:
        fix = run_step(ctx, f"p3.fix.{n}", lambda: _fix(ctx, n, chk["rev"], chk["fail_ids"]))
        iterations = n  # this iteration was actually run, whether or not it applied anything
        if not fix["applied"]:
            stop_reason = "no_candidate"  # no engine candidate cleared any of the remaining findings
            break
        new_model = DesignModel.model_validate(fix["model"])
        chk = run_step(ctx, f"p3.check.{n + 1}", lambda: _check(ctx, n + 1, chk["rev"], new_model, model, None))
        model, n = new_model, n + 1
    if chk["fail_ids"] and stop_reason is None:
        stop_reason = "exhausted"  # ran MAX_FIX_ITERATIONS and findings are still open
    run_step(ctx, S_DOCS, lambda: _docs(ctx, chk, iterations, stop_reason))
    return PhaseOutcome(gate="review", run_patch={"selected_option": sel})


def _select(ctx: PhaseContext) -> StepOutput:
    run = ctx.run()
    if run.get("selected_option"):
        return StepOutput(data={"option_id": run["selected_option"], "auto": False})
    options = [TopologyOption.model_validate(o) for o in run.get("options", [])]
    limit = lead_limit_weeks(ctx.scenario())
    opt = choose_option(options, ctx.outputs("p2.resolve_plan")["resolutions"], limit)
    if opt is None:
        raise ParkAtGate("option", "No option meets the resolved clauses with zero single points of failure and "
                                   "every lead time within the limit; choose one.")
    why = (f"Auto mode chose {opt.id}: it meets the resolved clauses with zero single points of failure and every "
           f"lead time within {limit} weeks, at the lowest cost.")
    res = ctx.agent(POWER, S_SELECT, f"{why} Explain this choice to the engineer in one sentence.")
    ctx.narrate(S_SELECT, "power", res.text if res else "", ctx.allowed(extra=[o.id for o in options]),
                "option selection", template=why)
    ctx.ledger(S_SELECT, "orchestrator", "did", why)
    ctx.deps.store.update_doc(ctx.run_path, {"selected_option": opt.id})
    return StepOutput(data={"option_id": opt.id, "auto": True})


def _route(ctx: PhaseContext, option_id: str) -> StepOutput:
    item = next(i for i in ctx.outputs("p2.annotate_options")["options"] if i["option"]["id"] == option_id)
    base, scn, box = DesignModel.model_validate(item["model"]), ctx.scenario(), {}

    def route_busways() -> dict:
        """Route feeders and row busways (and the default pipes) with the engine's default candidate routes."""
        box["model"] = ctx.deps.engine.route(scn, base)
        m = box["model"]
        return {"feeders": sorted(c.id for c in m.connections if c.kind != "internal" and c.route),
                "routed": sum(1 for c in m.connections if c.route)}

    tool = ctx.tool(S_ROUTE, "layout", route_busways)
    res = ctx.agent(LAYOUT, S_ROUTE, "Route the busways, then narrate the result.", tools=[tool])
    if "model" not in box:
        tool()
    m = box["model"]
    feeders = sorted(c.id for c in m.connections if c.kind != "internal" and c.route)
    routed = sum(1 for c in m.connections if c.route)
    # R14: code-authored, built only from the engine's route output.
    template = (f"Layout routed {_n(routed, 'connection')}, including {_n(len(feeders), 'feeder busway')}, "
                f"with the engine's default candidate routes.")
    ctx.narrate(S_ROUTE, "layout", res.text if res else "", ctx.allowed(m), "busway routing", template=template)
    ctx.emit(S_ROUTE, "cooling", "tool_result", "route_pipes done",
             payload={"tool": "route_pipes", "summary": {"pipes": {p.id: p.tier for p in m.pipes}}})
    ctx.emit(S_ROUTE, "cooling", "message", f"Cooling routed {len(m.pipes)} headers and branches on the pipe tiers")
    return StepOutput(data={"model": m.model_dump(mode="json")})


def _clashes(ctx: PhaseContext, model: DesignModel) -> StepOutput:
    def detect_clashes() -> dict:
        """Detect solid intersections between routed elements."""
        rep = ctx.deps.engine.detect_clashes(model)
        return {"count": len(rep.clashes), "clashes": rep.clashes[:20]}

    summary = ctx.tool(S_CLASH, "layout", detect_clashes)()
    ctx.emit(S_CLASH, "layout", "message", f"{summary['count']} solid clashes found")
    return StepOutput(data=summary)


def _boq(ctx: PhaseContext, model: DesignModel) -> StepOutput:
    box = {}

    def derive_pr_lines() -> dict:
        """Derive the BOQ and draft purchase-requisition lines from the model."""
        box["lines"] = ctx.deps.engine.derive_pr_lines(ctx.scenario(), model, ctx.erp())
        return {"lines": len(box["lines"]),
                "total_usd": round(sum(x.qty * x.unit_price for x in box["lines"]), 2)}

    ctx.tool(S_BOQ, "procurement", derive_pr_lines)()
    return StepOutput(data={"pr_lines": [x.model_dump(mode="json") for x in box["lines"]]})


def _check(ctx: PhaseContext, n: int, parent: str | None, model: DesignModel, parent_model: DesignModel | None,
           lines: list[dict] | None) -> StepOutput:
    step, scn, erp, box = f"p3.check.{n}", ctx.scenario(), ctx.erp(), {}
    pr = ([PRLine.model_validate(x) for x in lines] if lines is not None
          else ctx.deps.engine.derive_pr_lines(scn, model, erp))

    def run_rule_pack() -> dict:
        """Run the deterministic rule pack R01 to R15 (incl. R04b) on the revision."""
        box["findings"] = ctx.deps.engine.check(scn, model, erp, pr_lines=pr)
        fs = box["findings"]
        return {"checks": len(fs), **{s: sum(f.status == s for f in fs) for s in ("pass", "fail", "warn", "n/a")}}

    summary = ctx.tool(step, "checker", run_rule_pack)()
    findings = with_citation_boxes(box["findings"], ctx.deps.inputs().tender_pdf)
    fails = [f for f in findings if f.status == "fail"]
    rev, docs = build_revision(ctx, n, parent, model, findings,
                               f"{summary['checks']} checks, {summary['fail']} failing")
    # WS3 ruling R8: the revision artifact comes before its finding events, and each finding names its revision.
    ctx.emit(step, "checker", "artifact", f"Revision {rev.id} checked",
             payload={"type": "revision", "ref": f"{ctx.ws_path}/revisions/{rev.id}",
                      "changed": diff_elements(parent_model, model) if parent_model is not None else []})
    for f in fails:
        ctx.emit(step, "checker", "finding", f.title, detail=f"{f.rule_id} on {f.element_id}",
                 payload={"finding_id": f.id, "rule_id": f.rule_id, "element_id": f.element_id, "status": f.status,
                          "rev": rev.id})
    if not fails:
        ctx.metrics.setdefault("time_to_clean_s", ctx.active_s())
    return StepOutput(data={"rev": rev.id, "hash": rev.hash, "fail_ids": [f.id for f in fails],
                            "pr_lines": [x.model_dump(mode="json") for x in pr]}, docs=docs)


def _fix(ctx: PhaseContext, n: int, rev: str, fail_ids: list[str]) -> StepOutput:
    step, store, scn, erp = f"p3.fix.{n}", ctx.deps.store, ctx.scenario(), ctx.erp()
    model = load_revision_model(ctx.deps, ctx.uid, store.get_doc(f"{ctx.ws_path}/revisions/{rev}"))
    findings = [Finding.model_validate(store.get_doc(f"{ctx.ws_path}/revisions/{rev}/findings/{fid}"))
                for fid in fail_ids]
    allowed = ctx.allowed(model)

    def decide(f: Finding):
        owner = OWNER.get(f.rule_id, "checker")
        # P1-R7 (trust-critical): a FRESH engine lookup for THIS finding on the CURRENT model. The
        # agent's reply is only ever used as an id to look up in `cands` below; nothing from the LLM
        # output (a candidate id, a patch, metrics) is ever constructed into or merged onto a
        # FixCandidate -- only the engine's own objects, by identity, are ever applied.
        # Candidates are computed on THIS fix step's starting `model`, shared by every finding's parallel
        # `decide()` call below; fixes are then applied to `model` one at a time in sequence afterwards,
        # so any joint effect between two findings fixed in the same iteration only shows up at the next
        # check step (consistent with how R11's pipe metrics are reported).
        cands = ctx.deps.engine.fix_candidates(scn, model, f, erp)
        ctx.emit(step, owner, "tool_result", "fix_candidates done", payload={"tool": "fix_candidates", "summary": {
            "finding_id": f.id, "candidates": [{"id": c.id, "label": c.label, "cost_delta": c.cost_delta,
                                                "metrics": c.metrics} for c in cands]}})
        if not cands:
            return f, owner, None, [], None
        reply = None
        if owner in ("power", "cooling"):
            lines = "\n".join(f"- {c.id}: {c.label}; cost delta USD {c.cost_delta:,.0f}; metrics {c.metrics}"
                              for c in cands)
            msg = (f"Finding {f.id}: {f.title} on {f.element_id} (rule {f.rule_id}). Each engine candidate clears it "
                   f"without creating a new failure:\n{lines}\nChoose one by your criterion: {criterion(owner)}. "
                   'Reply with JSON {"candidate_id": id, "reason": one sentence naming the criterion}.')
            reply = ctx.agent_json(POWER if owner == "power" else COOLING, step, msg, FixChoice,
                                   key=f"{step}:{f.id}")
        # The reply's `candidate_id` is matched by id in this SAME fresh `cands` list -- an unknown or
        # forged id (never in `cands`) simply fails the lookup (`chosen` stays None) and falls through to
        # the engine's own `preferred_candidate` (R23) below.
        chosen = next((c for c in cands if reply is not None and c.id == reply.candidate_id), None)
        reason = reply.reason if chosen is not None else None
        chosen = chosen or preferred_candidate(owner, cands)
        return f, owner, chosen, [c for c in cands if c.id != chosen.id], reason

    with ThreadPoolExecutor(4) as pool:
        decisions = list(pool.map(decide, findings))
    docs, applied = [], []
    for f, owner, chosen, rejected, reason in decisions:
        if chosen is None:
            ctx.emit(step, "checker", "status", f"No engine candidate clears {f.id}")
            continue
        template = f"{AGENT_LABEL.get(owner, owner)} chose {chosen.id} for {f.id}: {criterion(owner)}."
        # placeholders=False: the stored reason is shown raw (FindingDrawer, calc report), never filled.
        text = (sanitize(reason, allowed | {chosen.id, *(c.id for c in rejected)}, template, placeholders=False)
                if reason else template)
        ctx.emit(step, owner, "message", text, payload={"finding_id": f.id, "candidate": chosen.id})
        alt = preferred_candidate(owner, rejected) if rejected else None
        f2 = f.model_copy(update={
            "fix": {"candidate": chosen.id, "label": chosen.label, "reason": text, "criterion": criterion(owner),
                    "agent": owner, "cost_delta": chosen.cost_delta,
                    "deltas": {**chosen.metrics, "cost_delta": chosen.cost_delta}},
            "rejected_fix": None if alt is None else {"candidate": alt.id, "label": alt.label,
                                                      "cost_delta": alt.cost_delta,
                                                      "deltas": {**alt.metrics, "cost_delta": alt.cost_delta}}})
        docs.append((f"{ctx.ws_path}/revisions/{rev}/findings/{f.id}", f2.model_dump(mode="json")))
        # Applied one at a time in sequence (not against a per-finding re-check): each `chosen` candidate
        # was computed on the model at the TOP of this fix step, so stacking effects between findings
        # fixed in this same iteration are only verified at the next check step.
        model = ctx.deps.engine.apply_fix(model, chosen)
        applied.append(chosen.id)
    return StepOutput(data={"applied": applied, "model": model.model_dump(mode="json")}, docs=docs)


def _docs(ctx: PhaseContext, chk: dict, iterations: int, stop_reason: str | None) -> StepOutput:
    store, ws = ctx.deps.store, ctx.ws_path
    rev_doc = store.get_doc(f"{ws}/revisions/{chk['rev']}")
    rev, model = Revision.model_validate(rev_doc), load_revision_model(ctx.deps, ctx.uid, rev_doc)
    stored_ledger = len(rev.ledger)  # entries appended below are written back to the revision doc at the end
    findings = [Finding.model_validate(d) for d in store.list_docs(f"{ws}/revisions/{rev.id}/findings")]
    fixes = [Finding.model_validate(d) for r in run_revisions(store, ctx.uid, ctx.rid)
             for d in store.list_docs(f"{ws}/revisions/{r['id']}/findings") if d.get("fix")]
    extra_docs: list[tuple[str, dict]] = []
    if chk["fail_ids"]:
        # Fix round 1, Important 3: the text must say what actually happened, since the ledger is the R16
        # audit trail. "Exhausted" only applies when every one of the MAX_FIX_ITERATIONS iterations was
        # actually run; if the loop broke early because no engine candidate cleared a remaining finding,
        # say that instead -- claiming "stopped after 2 iterations" when only 1 (or 0) ran would be false.
        open_findings = ", ".join(chk["fail_ids"])
        if stop_reason == "no_candidate":
            stop_text = (f"No engine candidate clears the remaining open findings; fix loop stopped after "
                        f"{iterations} iteration(s); open findings: {open_findings}. Approval is disabled.")
        else:
            stop_text = (f"Fix loop stopped after {MAX_FIX_ITERATIONS} iterations; open findings: "
                        f"{open_findings}. Approval is disabled.")
        ctx.ledger(S_DOCS, "checker", "did", stop_text)
        # Fix round 1, Minor: `_docs` runs AFTER the final revision was already built (and its `ledger`
        # gathered) in `_check`, so this stop/no-candidate entry would otherwise never reach the sign-off
        # ledger stored on that revision -- only the run-level event. Append it directly to the final
        # revision's own stored ledger (the audit trail of record) and write that revision doc again.
        rev = rev.model_copy(update={"ledger": [*rev.ledger, LedgerEntry(kind="did", agent="checker",
                                                                         text=stop_text)]})
    msg = (f"Revision {rev.id}: {len(findings)} checks, {len(chk['fail_ids'])} failing, {len(fixes)} fixes applied. "
           f"Report sections: {', '.join(SECTIONS)}. "
           'Reply with JSON {"order": [section ids], "summary": one sentence for the review page}.')
    reply = ctx.agent_json(DOCS, S_DOCS, msg, DocsReply)
    order = [x for x in (reply.order if reply else []) if x in SECTIONS]
    order += [x for x in SECTIONS if x not in order]
    # R14: code-authored, built only from the engine-checked findings and fixes counted above.
    template = (f"Docs prepared the calc report and BOQ for {rev.id}: {_n(len(findings), 'check')}, "
                f"{len(chk['fail_ids'])} failing, {_n(len(fixes), 'fix', 'fixes')} applied.")
    summary = ctx.narrate(S_DOCS, "docs", reply.summary if reply else "", ctx.allowed(model), "the calc report",
                          template=template)
    # P2 final fix wave (Task 18 minor): the arguments are built OUTSIDE the try, so a real bug -- missing
    # p1.intake outputs, a malformed option or PR line -- fails the step (resumable, visible) instead of being
    # reported as an export failure.
    args = dict(uid=ctx.uid, rev=rev, findings=findings, fixes=fixes,
                brief=DesignBrief.model_validate(ctx.outputs("p1.intake")["brief"]),
                options=[TopologyOption.model_validate(o) for o in ctx.run().get("options", [])],
                pr_lines=[PRLine.model_validate(x) for x in chk["pr_lines"]], order=order, summary=summary)
    try:
        files = (ctx.deps.exporter or StubExporter()).export(**args)
    except Exception:
        # A broken export (e.g. an unreachable blob store) must not fail the whole run: the review
        # gate still needs to be reachable. Degrade to a "failed" file status per file (rulings
        # R13/R26 cover this status value on the export artifact/status event), and say so on the
        # audit trail: the run's ledger events and the final revision's own stored ledger.
        log.exception("docs export failed for revision %s", rev.id)
        files = [{"name": n, "path": None, "status": "failed"} for n in ("calc-report.pdf", "boq.csv")]
        rev = rev.model_copy(update={"ledger": [*rev.ledger, ctx.ledger(S_DOCS, "docs", "did", EXPORT_FAILED)]})
    if len(rev.ledger) > stored_ledger:
        extra_docs.append((f"{ws}/revisions/{rev.id}", rev.model_dump(mode="json")))
    for f in files:
        if f.get("path"):  # storage path, served by GET /api/files/{path}
            ctx.emit(S_DOCS, "docs", "artifact", f"{f['name']} {f['status']}",
                     payload={"type": "export", "ref": f["path"], "name": f["name"], "status": f["status"]})
        else:
            ctx.emit(S_DOCS, "docs", "status", f"{f['name']} {f['status']}")
    return StepOutput(data={"rev": rev.id, "order": order, "summary": summary, "files": files}, docs=extra_docs)
