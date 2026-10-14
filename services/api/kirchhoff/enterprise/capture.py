"""Golden capture (spec §11, rulings W11/W17): a completed Hall B run in a visitor workspace → a signed static bundle
(Hall A; Pune Edge from a second run). export_run reads Firestore and the revision models in Cloud Storage (P2 R7);
to_static is a pure function of the raw capture, the target and the engine, so the same run always gives the same
bundle (spec §16 capture determinism)."""
import bisect
import hashlib
import json
import re
from typing import Any, Callable, Protocol

from pydantic import BaseModel, ConfigDict

from kirchhoff.contracts import (Approval, CrmOverlay, DesignBrief, DesignModel, Finding, Project, ProjectBundle,
                                 PurchaseRequisition, Revision, RunEvent, RunRecord, StepRecord)

from .world.config import HALL_A_PR_BASE, PUNE_PR_BASE
from .world.projects import REVIEWER, REVIEWER_ROLE, chip_what_ifs

HALL_B = Project(id="hall-b", name="Deccan AI Campus · Hall B", client="Deccan Compute", asset_pack="datahall",
                 state="signed", sample=True, updated_at=0.0)
MAX_GAP_S, GAP_S = 20.0, 2.0
VISITOR_NAME = "You (Demo Reviewer)"
LIVE_AUTHOR, CAPTURED_AUTHOR = "Kirchhoff agents", "Kirchhoff agents for Arjun Mehta"
DOCS_ORDER = ["summary", "requirements", "options", "findings", "fixes", "ledger", "boq"]
CALC_REPORT, BOQ = "calc-report.pdf", "boq.csv"


class CaptureError(RuntimeError):
    """The run is not a complete, signed golden run, or the rewrite would break an invariant."""


class CaptureTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: Project
    short_name: str  # replaces "Hall B" in narration
    run_id: str
    opportunity_id: str
    pr_base: int

    @property
    def files_url(self) -> str:
        return f"/demo/files/{self.project.id}"


HALL_A = CaptureTarget(project=Project(id="hall-a", name="Deccan AI Campus · Hall A", client="Deccan Compute",
                                       asset_pack="datahall", state="signed", sample=True, updated_at=0.0),
                       short_name="Hall A", run_id="run-hall-a-1", opportunity_id="opp-hall-a", pr_base=HALL_A_PR_BASE)
PUNE_EDGE = CaptureTarget(project=Project(id="pune-edge-1", name="Konkan Cloud · Pune Edge Phase 1",
                                          client="Konkan Cloud", asset_pack="datahall", state="signed", sample=True,
                                          updated_at=0.0),
                          short_name="Pune Edge Phase 1", run_id="run-pune-edge-1", opportunity_id="opp-pune-edge-1",
                          pr_base=PUNE_PR_BASE)
TARGETS = {t.project.id: t for t in (HALL_A, PUNE_EDGE)}


class RawCapture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rid: str
    bundle: ProjectBundle
    docs_order: list[str] = DOCS_ORDER
    docs_summary: str = ""


class CapturedBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle: ProjectBundle
    docs_order: list[str]
    docs_summary: str


class BlobReader(Protocol):
    def get(self, path: str) -> bytes: ...


def _model(cls, doc: dict):
    """Validate a Firestore doc into a frozen contract, ignoring keys WS2 adds beyond the contract."""
    return cls.model_validate({k: v for k, v in doc.items() if k in cls.model_fields})


def _walk(value: Any, fn: Callable[[str], str]) -> Any:
    if isinstance(value, str):
        return fn(value)
    if isinstance(value, dict):
        return {fn(k): _walk(v, fn) for k, v in value.items()}
    if isinstance(value, list):
        return [_walk(v, fn) for v in value]
    return value


def _outputs(store, blobs: BlobReader, run_path: str, step: str) -> dict | None:
    """Reads a step's committed outputs doc exactly as WS2's runs/outputs.py writes it: either the JSON is
    inlined ({"json": "<str>"}), or it was spilled to a content-addressed blob path that WS2 chose at write
    time ({"blob": "<path>", "sha256": "<digest>"}). The blob path is never reconstructed here -- it is read
    off the committed doc -- and the fetched bytes are sha256-verified before being trusted (matches WS2's
    runs/outputs.py:load_outputs, so a capture never silently accepts a corrupted or truncated blob)."""
    doc = store.get_doc(f"{run_path}/outputs/{step}")
    if doc is None:
        return None
    if "json" in doc:
        return json.loads(doc["json"])
    raw = blobs.get(doc["blob"])
    digest = hashlib.sha256(raw).hexdigest()
    if digest != doc["sha256"]:
        raise CaptureError(f"blob {doc['blob']} sha256 mismatch for step {step}: "
                           f"expected {doc['sha256']}, got {digest}")
    return json.loads(raw.decode("utf-8"))


def check_golden(raw: RawCapture) -> None:
    b, problems = raw.bundle, []
    run = b.runs[0] if b.runs else None
    if run is None or run.project_id != "hall-b" or run.status != "done":
        problems.append("the run is not a finished Hall B run")
    approved = [a for a in b.approvals if a.decision == "approved"]
    if len(approved) != 1:
        problems.append(f"expected exactly one approval, found {len(approved)}")
    else:
        signed = next((r for r in b.revisions if r.id == approved[0].revision), None)
        if signed is None or signed.status != "signed":
            problems.append("the approved revision is not signed")
        elif signed.check_summary.get("fail", 0):
            problems.append("the signed revision still has failing checks")
    if len(b.revisions) < 2:
        problems.append("a golden run has a failing first revision and a fixed one")
    if not b.prs or any(p.status != "submitted" for p in b.prs):
        problems.append("PRs are missing or not all submitted")
    if b.crm is None or b.crm.stage != "Design approved":
        problems.append("the CRM overlay is missing or not 'Design approved'")
    if not b.events:
        problems.append("no committed events")
    if problems:
        raise CaptureError("; ".join(problems))


def export_run(store, blobs: BlobReader, uid: str, rid: str) -> RawCapture:
    """Reads one completed, signed Hall B run from the visitor workspace exactly as WS2 writes it, and
    anonymises the uid. Events are ordered by their `seq` field (never by assuming contiguous seqs -- a new
    attempt may jump its seqs forward by WS2's SEQ_GAP), and only the attempt of each step that actually
    committed (status == "done") is kept; events from a stale, uncommitted attempt are dropped (P2 R4)."""
    ws, rp = f"workspaces/{uid}", f"workspaces/{uid}/runs/{rid}"
    run_doc = store.get_doc(rp)
    if run_doc is None:
        raise CaptureError(f"run {rid} not found in {ws}")
    run = _model(RunRecord, run_doc)
    steps = [_model(StepRecord, d) for d in store.list_docs(f"{rp}/steps")]
    done = {s.id: s.attempt for s in steps if s.status == "done"}
    events = [e for e in (_model(RunEvent, d) for d in store.list_docs(f"{rp}/events", order_by="seq"))
              if done.get(e.step) == e.attempt]  # only the attempt that committed each step (P2 R4)
    events.sort(key=lambda e: e.seq)  # order by the seq field itself, never by doc id contiguity
    intake = _outputs(store, blobs, rp, "p1.intake") or {}
    docs = _outputs(store, blobs, rp, "p3.docs") or {}
    prefix = f"{rid}-r"
    revisions: list[Revision] = []
    findings: dict[str, list[Finding]] = {}
    for d in store.list_docs(f"{ws}/revisions"):
        if not str(d.get("id", "")).startswith(prefix):
            continue
        rev = _model(Revision, d)
        model = rev.model or DesignModel.model_validate_json(blobs.get(f"{ws}/{rev.model_url}"))
        revisions.append(rev.model_copy(update={"model": model, "model_url": None}))
        findings[rev.id] = [_model(Finding, f) for f in store.list_docs(f"{ws}/revisions/{rev.id}/findings")]
    revisions.sort(key=lambda r: int(r.id[len(prefix):]))
    ids = {r.id for r in revisions}
    crm_doc = store.get_doc(f"{ws}/crm/opp-hall-b")
    bundle = ProjectBundle(
        project=HALL_B.model_copy(update={"updated_at": run.finished_at or run.started_at}),
        brief=DesignBrief.model_validate(intake["brief"]) if intake.get("brief") else None,
        runs=[run], steps=[s for s in steps if s.status == "done"], events=events, revisions=revisions,
        findings=findings,
        approvals=[_model(Approval, d) for d in store.list_docs(f"{ws}/approvals") if d.get("revision") in ids],
        prs=[_model(PurchaseRequisition, d) for d in store.list_docs(f"{ws}/prs") if d.get("revision") in ids],
        crm=_model(CrmOverlay, crm_doc) if crm_doc else None)
    raw = RawCapture(rid=rid, bundle=bundle, docs_order=docs.get("order") or DOCS_ORDER,
                     docs_summary=docs.get("summary", ""))
    anonymous = RawCapture.model_validate(_walk(raw.model_dump(mode="json"), lambda s: s.replace(uid, "visitor")))
    check_golden(anonymous)
    return anonymous


def _times(b: ProjectBundle) -> list[float]:
    ts = [e.ts for e in b.events] + [a.ts for a in b.approvals] + [p.created_at for p in b.prs]
    ts += [r.created_at for r in b.revisions]
    for run in b.runs:
        ts += [run.started_at] + ([run.finished_at] if run.finished_at is not None else [])
    for s in b.steps:
        ts += [s.started_at] + ([s.finished_at] if s.finished_at is not None else [])
    if b.crm:
        ts.append(b.crm.updated_at)
    return ts


def time_map(times: list[float], anchor_from: float, anchor_to: float) -> Callable[[float], float]:
    """Monotone map: gaps longer than MAX_GAP_S (people waiting at gates) shrink to GAP_S; anchor_from → anchor_to."""
    pts = sorted(set(times) | {anchor_from})
    acc, out = 0.0, {}
    for i, t in enumerate(pts):
        if i:
            gap = t - pts[i - 1]
            acc += GAP_S if gap > MAX_GAP_S else gap
        out[t] = acc
    offset = anchor_to - out[anchor_from]

    def m(t: float) -> float:
        if t in out:
            return round(out[t] + offset, 3)
        base = pts[max(bisect.bisect_right(pts, t) - 1, 0)]
        return round(out[base] + min(max(t - base, 0.0), GAP_S) + offset, 3)

    return m


def to_static(raw: RawCapture, engine, scn, erp, *, target: CaptureTarget, signed_at: float) -> CapturedBundle:
    check_golden(raw)
    b, pid = raw.bundle, target.project.id
    prefix = f"{raw.rid}-r"
    rev_map = {r.id: f"r{r.id[len(prefix):]}" for r in b.revisions}
    pr_map = {p.id: f"PR-2026-{target.pr_base + i:04d}"
              for i, p in enumerate(sorted(b.prs, key=lambda p: (p.created_at, p.id)))}
    swaps = sorted({**rev_map, **pr_map, raw.rid: target.run_id}.items(), key=lambda kv: (-len(kv[0]), kv[0]))
    approval = next(a for a in b.approvals if a.decision == "approved")
    tmap = time_map(_times(b), approval.ts, signed_at)

    def text(s: str) -> str:
        for old, new in swaps:
            s = s.replace(old, new)
        s = re.sub(r"exports/r\d+/calc-report\.pdf", f"{target.files_url}/{CALC_REPORT}", s)
        s = re.sub(r"exports/r\d+/boq\.csv", f"{target.files_url}/{BOQ}", s)
        s = s.replace("workspaces/visitor/", f"seed/{pid}/")
        s = s.replace(HALL_B.name, target.project.name).replace("opp-hall-b", target.opportunity_id)
        s = s.replace("hall-b", pid).replace("Hall B", target.short_name)
        return s.replace(VISITOR_NAME, REVIEWER)

    models = {rev_map[r.id]: r.model for r in b.revisions}
    run_hash = {rev_map[r.id]: r.hash for r in b.revisions}
    data = b.model_dump(mode="json")
    for r in data["revisions"]:
        r["model"] = None  # models are never rewritten, so their hashes survive (P2 R22)
    out = ProjectBundle.model_validate(_walk(data, text))
    signed_rev = rev_map[approval.revision]

    revisions = []
    for r in out.revisions:
        h = engine.model_hash(models[r.id])
        if h != run_hash[r.id]:
            raise CaptureError(f"{r.id}: engine hash {h[:12]} differs from the run's {run_hash[r.id][:12]} (P2 R22)")
        revisions.append(r.model_copy(update={
            "project_id": pid, "model": models[r.id], "model_url": None, "hash": h, "created_at": tmap(r.created_at),
            "author": CAPTURED_AUTHOR if r.author == LIVE_AUTHOR else r.author,
            "status": "signed" if r.id == signed_rev else r.status}))
    r0 = out.runs[0]
    run = r0.model_copy(update={"id": target.run_id, "project_id": pid, "status": "done", "gate": None, "lease": None,
                                "started_at": tmap(r0.started_at),
                                "finished_at": tmap(r0.finished_at) if r0.finished_at is not None else None})
    steps = sorted((s.model_copy(update={"started_at": tmap(s.started_at),
                                         "finished_at": tmap(s.finished_at) if s.finished_at is not None else None})
                    for s in out.steps), key=lambda s: (s.started_at, s.id))
    events = [e.model_copy(update={"seq": i + 1, "ts": tmap(e.ts)})
              for i, e in enumerate(sorted(out.events, key=lambda e: e.seq))]
    approvals = [a.model_copy(update={"id": f"appr-{pid}-1", "approver_name": REVIEWER, "role": REVIEWER_ROLE,
                                      "ts": tmap(a.ts), "comment": a.comment or "Approved for procurement."})
                 for a in out.approvals if a.decision == "approved"]
    prs = sorted((p.model_copy(update={"project_id": pid, "status": "submitted", "created_at": tmap(p.created_at)})
                  for p in out.prs), key=lambda p: p.id)
    crm = out.crm.model_copy(update={"opportunity_id": target.opportunity_id, "updated_at": tmap(out.crm.updated_at)})
    what_ifs = chip_what_ifs(engine, scn, models[signed_rev], erp, f"seed:{pid}@{signed_rev}", required=True)
    last = max([e.ts for e in events] + [a.ts for a in approvals] + [p.created_at for p in prs] + [crm.updated_at])
    bundle = ProjectBundle(project=target.project.model_copy(update={"updated_at": last}),
                           brief=out.brief.model_copy(update={"project_id": pid}) if out.brief else None,
                           runs=[run], steps=steps, events=events, revisions=revisions, findings=out.findings,
                           approvals=approvals, prs=prs, crm=crm, what_ifs=what_ifs)
    _check_rewritten(bundle, raw.rid, signed_rev)
    return CapturedBundle(bundle=bundle, docs_order=list(raw.docs_order), docs_summary=text(raw.docs_summary))


def to_hall_a(raw: RawCapture, engine, scn, erp, *, signed_at: float) -> CapturedBundle:
    return to_static(raw, engine, scn, erp, target=HALL_A, signed_at=signed_at)


def _check_rewritten(bundle: ProjectBundle, rid: str, signed_rev: str) -> None:
    no_models = bundle.model_copy(update={"revisions": [r.model_copy(update={"model": None}) for r in bundle.revisions]})
    dump = no_models.model_dump_json()
    leaks = [s for s in ("hall-b", "Hall B", VISITOR_NAME, rid) if s in dump]
    if leaks:
        raise CaptureError(f"the rewrite left {leaks} in the {bundle.project.id} bundle")
    ids = {r.id for r in bundle.revisions}
    if (bundle.approvals[0].revision != signed_rev or any(p.revision not in ids for p in bundle.prs)
            or set(bundle.findings) - ids):
        raise CaptureError("approval, PRs or findings point at unknown revisions")


def render_capture_docs(cap: CapturedBundle, engine, scn, erp) -> dict[str, bytes]:
    """The project's calc report and BOQ (ruling W11). Uses WS2's renderer when it is available."""
    b = cap.bundle
    signed = next(r for r in b.revisions if r.status == "signed")
    lines = engine.derive_pr_lines(scn, signed.model, erp)
    fixes = [f for rev in sorted(b.findings) for f in b.findings[rev] if f.fix]
    summary = cap.docs_summary or signed.summary
    try:
        from kirchhoff.agents.docs_export import boq_csv, calc_report_pdf  # WS2 P2 Task 18
    except ImportError:
        from .world.docs import boq_csv_bytes, summary_pdf

        rows = [("Revision", f"{signed.id} · hash {signed.hash[:16]}"), ("Topology", signed.model.topology),
                ("Checks", ", ".join(f"{k} {v}" for k, v in signed.check_summary.items())),
                ("Fixes", "; ".join(f"{f.id}: {f.fix['label']}" for f in fixes) or "none"),
                ("Approved by", f"{b.approvals[0].approver_name} ({b.approvals[0].role})")]
        return {CALC_REPORT: summary_pdf(f"Kirchhoff calc report · {b.project.name}", summary, rows),
                BOQ: boq_csv_bytes(lines)}
    pdf = calc_report_pdf(rev=signed, findings=b.findings.get(signed.id, []), fixes=fixes, brief=b.brief,
                          options=b.runs[0].options if b.runs else [], pr_lines=lines, order=cap.docs_order,
                          summary=summary)
    return {CALC_REPORT: pdf, BOQ: boq_csv(lines)}


class GcsReader:
    """Reads revision models and large step outputs from the Firebase bucket (CLI only)."""

    def __init__(self, bucket: str = "ordinal-mep.firebasestorage.app") -> None:
        self._name, self._bucket = bucket, None

    def get(self, path: str) -> bytes:
        if self._bucket is None:
            from google.cloud import storage
            self._bucket = storage.Client(project="ordinal-mep").bucket(self._name)
        return self._bucket.blob(path).download_as_bytes()


def find_workspace_for_run(db, rid: str) -> str:
    """The run id is in the UI's URL (?run=); the uid is not, so look it up (CLI only)."""
    for ref in db.collection("workspaces").list_documents():
        if ref.collection("runs").document(rid).get().exists:
            return ref.id
    raise CaptureError(f"no workspace holds run {rid}")
