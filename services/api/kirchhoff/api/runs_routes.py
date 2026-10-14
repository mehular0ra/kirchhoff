import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from kirchhoff.contracts import Approval, OpenQuestion, PlanStep, RunRecord, TopologyId
from kirchhoff.runs.deps import Deps
from kirchhoff.runs.leases import CapReached, run_path
from kirchhoff.runs.orchestrator import (GateExpired, LeaseBusy, WrongState, ensure_gate, resume_from_gate,
                                        resume_run, start_phase)
from kirchhoff.runs.revisions import latest_revision

from .errors import err

RUNS_PER_HOUR = 5


class RunCreate(BaseModel):
    project_id: Literal["hall-b"]
    autonomy: Literal["ask", "auto"] = "ask"


class PlanGate(BaseModel):
    answers: dict[str, str] = {}
    plan_notes: dict[str, str] = {}


class OptionGate(BaseModel):
    option_id: TopologyId


REVIEWER_NAME, REVIEWER_ROLE = "You (Demo Reviewer)", "Reviewer"


class ReviewGate(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: str = ""


def make_router(deps: Deps, current_uid) -> APIRouter:
    router = APIRouter()

    def advance(uid: str, rid: str, gate: str, patch: dict):
        try:
            resume_from_gate(deps, uid, rid, gate, patch)
        except WrongState:
            return err(409, "wrong_state")
        except GateExpired:
            return err(409, "gate_expired")
        except LeaseBusy:
            return err(409, "run_in_progress")
        except CapReached:
            return err(429, "global_cap", offer="replay")
        return {"ok": True}

    def at_gate(run: dict, gate: str) -> bool:
        return run.get("status") == "at_gate" and run.get("gate") == gate

    @router.post("/api/runs", status_code=202)
    def create_run(body: RunCreate, uid: str = Depends(current_uid)):
        now, ws_path = deps.clock(), f"workspaces/{uid}"
        ws = deps.store.get_doc(ws_path) or {}
        recent = [t for t in ws.get("run_starts", []) if now - t < 3600]
        if len(recent) >= RUNS_PER_HOUR:
            return err(429, "visitor_rate_limit")
        rid = uuid.uuid4().hex[:12]
        deps.store.set_doc(run_path(uid, rid), RunRecord(id=rid, project_id=body.project_id, status="running",
                                                         autonomy=body.autonomy, phase="p1",
                                                         started_at=now).model_dump(mode="json"))
        try:
            start_phase(deps, uid, rid, "p1")
        except CapReached:
            deps.store.delete_tree(run_path(uid, rid))
            return err(429, "global_cap", offer="replay")
        deps.store.update_doc(ws_path, {"created_at": ws.get("created_at", now), "last_run_at": now,
                                        "run_starts": recent + [now]})
        return {"run_id": rid}

    @router.post("/api/runs/{rid}/gates/plan", status_code=202)
    def gate_plan(rid: str, body: PlanGate, uid: str = Depends(current_uid)):
        run = deps.store.get_doc(run_path(uid, rid))
        if run is None:
            return err(404, "run_not_found")
        if not at_gate(run, "plan"):
            return err(409, "wrong_state")
        qs = {q["id"]: OpenQuestion.model_validate(q) for q in run.get("open_questions", [])}
        for qid, value in body.answers.items():
            if qid not in qs or value not in qs[qid].options:
                return err(422, "invalid_answer", question_id=qid)
        questions = [(q.model_copy(update={"resolution": body.answers[q.id]}) if q.id in body.answers else q)
                     .model_dump(mode="json") for q in qs.values()]
        plan = [PlanStep.model_validate(p) for p in run.get("plan", [])]
        plan = [(p.model_copy(update={"note": body.plan_notes[p.id]}) if p.id in body.plan_notes else p).model_dump()
                for p in plan]
        return advance(uid, rid, "plan", {"open_questions": questions, "plan": plan})

    @router.post("/api/runs/{rid}/gates/option", status_code=202)
    def gate_option(rid: str, body: OptionGate, uid: str = Depends(current_uid)):
        run = deps.store.get_doc(run_path(uid, rid))
        if run is None:
            return err(404, "run_not_found")
        if not at_gate(run, "option"):
            return err(409, "wrong_state")
        if body.option_id not in {o["id"] for o in run.get("options", [])}:
            return err(422, "option_not_offered")
        return advance(uid, rid, "option", {"selected_option": body.option_id})

    @router.post("/api/runs/{rid}/resume", status_code=202)
    def resume(rid: str, uid: str = Depends(current_uid)):
        if deps.store.get_doc(run_path(uid, rid)) is None:
            return err(404, "run_not_found")
        try:
            return {"resumed": resume_run(deps, uid, rid)}
        except CapReached:
            return err(429, "global_cap", offer="replay")

    @router.post("/api/runs/{rid}/gates/review", status_code=202)
    def gate_review(rid: str, body: ReviewGate, uid: str = Depends(current_uid)):
        try:
            ensure_gate(deps, uid, rid, "review")
        except KeyError:
            return err(404, "run_not_found")
        except WrongState:
            return err(409, "wrong_state")
        except GateExpired:
            return err(409, "gate_expired")
        rev = latest_revision(deps.store, uid, rid)
        if rev is None:
            return err(409, "wrong_state")
        if body.decision == "approved" and (rev.get("check_summary") or {}).get("fail", 0) > 0:
            return err(409, "open_findings")
        now = deps.clock()
        appr = Approval(id=uuid.uuid4().hex[:12], revision=rev["id"], approver_name=REVIEWER_NAME, role=REVIEWER_ROLE,
                        decision=body.decision, comment=body.comment, ts=now)
        deps.store.set_doc(f"workspaces/{uid}/approvals/{appr.id}", appr.model_dump(mode="json"))
        if body.decision == "rejected":
            deps.store.update_doc(run_path(uid, rid), {"status": "done", "gate": None, "finished_at": now})
            return {"ok": True}
        deps.store.update_doc(f"workspaces/{uid}/revisions/{rev['id']}", {"status": "signed"})
        return advance(uid, rid, "review", {})

    return router
