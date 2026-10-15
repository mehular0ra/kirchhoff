"""P1: Intake → Orchestrator → PLAN GATE (spec §6.2)."""
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel

from kirchhoff.agents.specs import ORCHESTRATOR
from kirchhoff.contracts import DesignBrief, PlanStep
from kirchhoff.intake.brief import build_brief
from kirchhoff.intake.drawing import DxfSummary, compare_drawing, parse_dxf_geometry
from kirchhoff.intake.extract import extract_tender, read_drawing
from kirchhoff.intake.score import load_ground_truth, score_intake
from kirchhoff.intake.verify import PdfText, clause_on_page, verify_quote

from .policy import PLAN_TEMPLATE
from .steps import PhaseContext, PhaseOutcome, StepOutput, _n, run_step

DOC_ID = "tender-hall-a"
S_INTAKE, S_PLAN = "p1.intake", "p1.plan"


class PlanReply(BaseModel):
    summary: str
    ask_human: list[str] = []


def run_p1(ctx: PhaseContext) -> PhaseOutcome:
    brief = DesignBrief.model_validate(run_step(ctx, S_INTAKE, lambda: _intake(ctx))["brief"])
    plan = run_step(ctx, S_PLAN, lambda: _plan(ctx, brief))
    return PhaseOutcome(gate="plan", run_patch={"plan": plan["plan"], "open_questions": plan["open_questions"]})


def _intake(ctx: PhaseContext) -> StepOutput:
    files = ctx.deps.inputs()
    # P2 final fix wave (Important 4): the ERP ids are fetched BEFORE the 60-240 s intake call, so an ERP
    # outage with no cached snapshot fails the step fast (resumable) instead of after the tokens are spent.
    allowed = ctx.allowed()
    ctx.emit(S_INTAKE, "intake", "status", "Reading the tender and the hall drawing")
    with ThreadPoolExecutor(2) as pool:
        f_tender = pool.submit(extract_tender, ctx.deps.runner, files.tender_pdf.read_bytes())
        f_drawing = pool.submit(read_drawing, ctx.deps.runner, files.plan_pdf.read_bytes())
        extraction, r_tender = f_tender.result()  # Intake is critical: failure fails the step (resume retries)
        try:
            drawing, r_drawing = f_drawing.result()
        except Exception as exc:
            drawing, r_drawing = None, None
            ctx.emit(S_INTAKE, "intake", "status", "Drawing could not be read", detail=type(exc).__name__)
    ctx.add_tokens(r_tender, r_drawing)
    with PdfText(files.tender_pdf) as pdf:
        def verify(page, quote, value, unit=None):
            chk = verify_quote(pdf, page, quote, value, unit)
            ctx.emit(S_INTAKE, "intake", "tool_result", "Quote verified" if chk.ok else "Quote rejected",
                     detail=f"page {page}",
                     payload={"tool": "verify_quote", "summary": {"page": page, "ok": chk.ok, "reason": chk.reason}})
            return chk

        def on_backstop(q):
            ctx.ledger(S_INTAKE, "intake", "assumed",
                       f"{q.id} added by the deterministic topology backstop (ruling P2-R13): the model "
                       "did not report this verified clause conflict itself.")

        brief = build_brief(ctx.run().get("project_id", "hall-b"), DOC_ID, extraction, verify, {}, allowed,
                            on_backstop, clause_printed=lambda page, label: clause_on_page(pdf, page, label))
    def parse_dxf_geometry_tool() -> dict:
        """Parse the hall DXF: grid labels and overall size."""
        return parse_dxf_geometry(files.dxf).model_dump(mode="json")

    parse_dxf_geometry_tool.__name__ = "parse_dxf_geometry"  # event and tool name
    dxf = DxfSummary.model_validate(ctx.tool(S_INTAKE, "intake", parse_dxf_geometry_tool)())
    check = compare_drawing(drawing, dxf) if drawing else {
        "agrees": False, "differences": ["drawing could not be read"], "grid_x": dxf.grid_x, "grid_y": dxf.grid_y,
        "overall_mm": list(dxf.overall_mm)}
    brief = brief.model_copy(update={"drawing_check": check})
    if files.ground_truth.exists():
        brief = brief.model_copy(update={"intake_score": score_intake(brief, load_ground_truth(files.ground_truth))})
    n_ok, n = sum(r.verified for r in brief.requirements), len(brief.requirements)
    ctx.emit(S_INTAKE, "intake", "message", f"{n_ok}/{n} quotes verified", payload={"verified": n_ok, "total": n})
    ctx.emit(S_INTAKE, "intake", "message",
             "Drawing read · DXF agrees" if check["agrees"] else "Drawing read · differences found",
             detail="; ".join(check["differences"]), payload={"drawing_check": check})
    for q in brief.open_questions:
        ctx.emit(S_INTAKE, "intake", "status", "Contradiction found", detail=q.text, payload={"question_id": q.id})
    ctx.emit(S_INTAKE, "intake", "artifact", "Design brief ready",
             payload={"type": "brief", "ref": f"{ctx.run_path}/outputs/{S_INTAKE}"})
    ctx.metrics.update({"quotes_verified": float(n_ok), "quotes_total": float(n),
                        "intake_recall": float(brief.intake_score.get("recall", 0.0))})
    return StepOutput(data={"brief": brief.model_dump(mode="json")})


def _plan(ctx: PhaseContext, brief: DesignBrief) -> StepOutput:
    reqs = "\n".join(f"- {r.id} cites {r.citation.clause or 'an unlabelled clause'}"
                     for r in brief.requirements if r.verified)
    qs = "\n".join(f"- {q.id}: {q.text} Options: {', '.join(q.options)}. Default: {q.default_resolution}."
                   for q in brief.open_questions) or "- none"
    msg = (f"Design brief for an AI data hall.\nVerified requirements:\n{reqs}\nOpen questions:\n{qs}\n"
           'Reply with JSON {"summary": one sentence, "ask_human": [ids of the questions the engineer must decide]}.')
    reply = ctx.agent_json(ORCHESTRATOR, S_PLAN, msg, PlanReply)
    ask = set(reply.ask_human) if reply else {q.id for q in brief.open_questions}
    questions = []
    for q in brief.open_questions:
        if q.id not in ask:
            q = q.model_copy(update={"resolution": q.default_resolution})
            ctx.ledger(S_PLAN, "orchestrator", "assumed",
                       f"{q.id} resolved to {q.default_resolution}: the main body governs over the appendix.")
        questions.append(q.model_dump(mode="json"))
    plan = [PlanStep(id=sid, agent=agent, title=title).model_dump() for sid, agent, title in PLAN_TEMPLATE]
    ctx.emit(S_PLAN, "orchestrator", "plan", "Plan ready", payload={"plan": plan, "open_questions": questions})
    if reply:
        n_verified = sum(r.verified for r in brief.requirements)
        template = (f"Orchestrator built a {len(plan)}-step plan from {_n(n_verified, 'verified requirement')}, "
                    f"with {_n(len(ask), 'question')} for you to decide.")
        ctx.narrate(S_PLAN, "orchestrator", reply.summary, ctx.allowed(extra=[q.id for q in brief.open_questions]),
                    "planning", template=template)
    return StepOutput(data={"plan": plan, "open_questions": questions})
