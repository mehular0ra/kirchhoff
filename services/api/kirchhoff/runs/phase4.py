"""P4 (on approval): sign → PRs via the enterprise client → R12 on submitted PRs → CRM stage → audit (spec §6.2)."""
from collections import defaultdict

from kirchhoff.agents.ports import HALL_B_OPPORTUNITY_ID, STAGE_DESIGN_APPROVED
from kirchhoff.contracts import Approval, PurchaseRequisition

from .policy import REVIEWER_NAME, REVIEWER_ROLE
from .revisions import load_revision_model
from .steps import PhaseContext, PhaseOutcome, StepOutput, run_step

S_SIGN, S_PRS, S_R12, S_CRM, S_AUDIT = "p4.sign", "p4.create_prs", "p4.r12_recheck", "p4.crm", "p4.audit"


def run_p4(ctx: PhaseContext) -> PhaseOutcome:
    sign = run_step(ctx, S_SIGN, lambda: _sign(ctx))
    prs = run_step(ctx, S_PRS, lambda: _create_prs(ctx, sign))["prs"]
    blocked = run_step(ctx, S_R12, lambda: _r12(ctx, sign, prs))["blocked"]
    if not blocked:
        run_step(ctx, S_CRM, lambda: _crm(ctx))
    run_step(ctx, S_AUDIT, lambda: _audit(ctx, sign, prs, blocked))
    return PhaseOutcome(gate=None, metrics={"prs": float(len(prs)), "p4_blocked": float(blocked)})


def _model(ctx: PhaseContext, rev: str):
    return load_revision_model(ctx.deps, ctx.uid, ctx.deps.store.get_doc(f"{ctx.ws_path}/revisions/{rev}"))


def _sign(ctx: PhaseContext) -> StepOutput:
    """Important 1 (fix round 1): the approval doc and the signed revision are written HERE, under this
    step's own lease-checked commit, not by the route that claimed the gate. The route only patches the
    run doc's `review` field (approval id, comment, ts, the rev it approved) before claiming the lease;
    this step reads that patch back and is the sole writer of the approval + signed-revision docs, which
    makes a retry of this very step idempotent (same id, same content, same path -- not a second doc)."""
    review = ctx.run().get("review") or {}
    rev_id = review["rev"]  # the rev the engineer actually approved, not whatever is "latest" right now
    rev = ctx.deps.store.get_doc(f"{ctx.ws_path}/revisions/{rev_id}")
    appr = Approval(id=review["approval_id"], revision=rev_id, approver_name=REVIEWER_NAME, role=REVIEWER_ROLE,
                    decision="approved", comment=review.get("comment", ""), ts=review["ts"])
    ctx.ledger(S_SIGN, "system", "did",
               f"{rev_id} signed by {appr.approver_name} ({appr.role}); hash {rev['hash'][:12]}")
    signed = {**rev, "status": "signed"}
    return StepOutput(data={"rev": rev_id, "hash": rev["hash"], "approval_id": appr.id},
                      docs=[(f"{ctx.ws_path}/approvals/{appr.id}", appr.model_dump(mode="json")),
                            (f"{ctx.ws_path}/revisions/{rev_id}", signed)])


def _create_prs(ctx: PhaseContext, sign: dict) -> StepOutput:
    scn, erp = ctx.scenario(), ctx.erp()
    lines = ctx.deps.engine.derive_pr_lines(scn, _model(ctx, sign["rev"]), erp)
    by_vendor = defaultdict(list)
    for line in lines:
        by_vendor[erp.get(line.material_id).vendor].append(line)
    project_id, prs = ctx.run().get("project_id", "hall-b"), []

    def erp_create_pr(vendor: str) -> dict:
        """Submit one purchase requisition per vendor to the ERP sandbox."""
        pr = ctx.deps.enterprise.create_pr(ctx.uid, project_id, sign["rev"], by_vendor[vendor],
                                           idempotency_key=f"{ctx.rid}:{sign['rev']}:{vendor}")
        prs.append(pr)
        return {"pr_id": pr.id, "lines": len(pr.lines), "status": pr.status}

    tool = ctx.tool(S_PRS, "procurement", erp_create_pr)
    for vendor in sorted(by_vendor):
        tool(vendor=vendor)
    ctx.emit(S_PRS, "procurement", "message", f"Procurement submitted {len(prs)} purchase requisitions to the ERP")
    return StepOutput(data={"prs": [pr.model_dump(mode="json") for pr in prs]},
                      docs=[(f"{ctx.ws_path}/prs/{pr.id}", pr.model_dump(mode="json")) for pr in prs])


def _r12(ctx: PhaseContext, sign: dict, prs: list[dict]) -> StepOutput:
    scn, erp, box = ctx.scenario(), ctx.erp(), {}
    submitted = [PurchaseRequisition.model_validate(p) for p in prs]
    lines = [line for pr in submitted for line in pr.lines]
    model = _model(ctx, sign["rev"])

    def check_submitted_prs() -> dict:
        """Re-run R12 (SLD = BOQ = PR lines) against the submitted purchase requisitions."""
        box["r12"] = [f for f in ctx.deps.engine.check(scn, model, erp, pr_lines=lines) if f.rule_id == "R12"]
        return {"r12": [{"id": f.id, "status": f.status} for f in box["r12"]]}

    ctx.tool(S_R12, "checker", check_submitted_prs)()
    failed = [f for f in box["r12"] if f.status == "fail"]
    if not failed:
        ctx.emit(S_R12, "checker", "message", "R12 passes on the submitted PRs")
        return StepOutput(data={"blocked": False})
    docs = []
    for pr in submitted:
        ctx.deps.enterprise.set_pr_status(ctx.uid, pr.id, "blocked")
        docs.append((f"{ctx.ws_path}/prs/{pr.id}", pr.model_copy(update={"status": "blocked"}).model_dump(mode="json")))
    finding = failed[0].model_copy(update={"id": "R12:submitted-prs", "element_id": "submitted-prs"})
    docs.append((f"{ctx.ws_path}/revisions/{sign['rev']}/findings/{finding.id}", finding.model_dump(mode="json")))
    ctx.emit(S_R12, "checker", "finding", finding.title, detail="R12 on submitted-prs",
             payload={"finding_id": finding.id, "rule_id": "R12", "element_id": "submitted-prs", "status": "fail",
                      "rev": sign["rev"]})
    ctx.ledger(S_R12, "system", "did",
               "PR submission blocked: R12 failed on the submitted PRs; the signed revision stays signed.")
    return StepOutput(data={"blocked": True}, docs=docs)


def _crm(ctx: PhaseContext) -> StepOutput:
    box = {}

    def update_crm_opportunity() -> dict:
        """Move the Hall B opportunity to Design approved in the CRM sandbox."""
        box["ov"] = ctx.deps.enterprise.set_opportunity_stage(ctx.uid, HALL_B_OPPORTUNITY_ID, STAGE_DESIGN_APPROVED)
        return {"opportunity_id": HALL_B_OPPORTUNITY_ID, "stage": STAGE_DESIGN_APPROVED}

    ctx.tool(S_CRM, "system", update_crm_opportunity)()
    ov = box["ov"]
    ctx.emit(S_CRM, "system", "message", f"CRM opportunity moved to {ov.stage}")
    return StepOutput(data={"stage": ov.stage},
                      docs=[(f"{ctx.ws_path}/crm/{ov.opportunity_id}", ov.model_dump(mode="json"))])


def _audit(ctx: PhaseContext, sign: dict, prs: list[dict], blocked: bool) -> StepOutput:
    text = (f"Approval {sign['approval_id']} recorded for {sign['rev']} (hash {sign['hash'][:12]}); {len(prs)} PRs "
            + ("blocked by R12; CRM unchanged." if blocked else "submitted; CRM moved to Design approved."))
    ctx.ledger(S_AUDIT, "system", "did", text)
    return StepOutput(data={"text": text})
