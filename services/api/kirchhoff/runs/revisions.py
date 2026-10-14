"""Revisions (spec §14): model in Cloud Storage (R7), engine hash (R22), findings as subcollection docs."""
import threading
from pathlib import Path

from kirchhoff.contracts import Citation, DesignModel, Finding, LedgerEntry, Revision
from kirchhoff.intake.verify import PdfText
from kirchhoff.store import Store

from .deps import Deps
from .steps import PhaseContext

LIVE_AUDIO_NOTE = LedgerEntry(kind="not_checked", agent="copilot",
                              text="Spoken Gemini Live audio is not digit-filtered; on-screen transcripts are.")


def rev_id(rid: str, n: int) -> str:
    return f"{rid}-r{n}"


def model_blob_path(uid: str, rev: str) -> str:
    return f"workspaces/{uid}/revisions/{rev}/model.json"


def gather_ledger(ctx: PhaseContext) -> list[LedgerEntry]:
    ctx.events.flush()
    store = ctx.deps.store
    attempts = {d["id"]: d.get("attempt") for d in store.list_docs(f"{ctx.run_path}/steps")}
    seen, out = set(), []
    for e in store.list_docs(f"{ctx.run_path}/events"):
        if e.get("kind") != "ledger" or attempts.get(e.get("step")) != e.get("attempt"):
            continue
        entry = LedgerEntry.model_validate(e["payload"]["entry"])
        if entry.text not in seen:
            seen.add(entry.text)
            out.append(entry)
    return out


def build_revision(ctx: PhaseContext, n: int, parent: str | None, model: DesignModel, findings: list[Finding],
                   summary: str) -> tuple[Revision, list[tuple[str, dict]]]:
    rid = rev_id(ctx.rid, n)
    ctx.deps.blobs.put(model_blob_path(ctx.uid, rid), model.model_dump_json().encode("utf-8"), "application/json")
    counts = {s: sum(f.status == s for f in findings) for s in ("pass", "fail", "warn", "n/a")}
    ledger = gather_ledger(ctx) + [LedgerEntry(kind="not_checked", agent="checker", text=t)
                                   for t in ctx.deps.engine.ledger_not_checked()] + [LIVE_AUDIO_NOTE]
    rev = Revision(id=rid, project_id=ctx.run().get("project_id", "hall-b"), parent=parent, author="Kirchhoff agents",
                   hash=ctx.deps.engine.model_hash(model), model=None, model_url=f"revisions/{rid}/model.json",
                   summary=summary, check_summary=counts, status="checked", ledger=ledger, created_at=ctx.deps.clock())
    docs = [(f"{ctx.ws_path}/revisions/{rid}", rev.model_dump(mode="json"))]
    docs += [(f"{ctx.ws_path}/revisions/{rid}/findings/{f.id}", f.model_dump(mode="json")) for f in findings]
    return rev, docs


def load_revision_model(deps: Deps, uid: str, rev_doc: dict) -> DesignModel:
    if rev_doc.get("model"):
        return DesignModel.model_validate(rev_doc["model"])
    return DesignModel.model_validate_json(deps.blobs.get(f"workspaces/{uid}/{rev_doc['model_url']}"))


def diff_elements(old: DesignModel, new: DesignModel) -> list[str]:
    def index(m: DesignModel) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for group in (m.equipment, m.connections, m.pipes, m.cooling_nodes, m.racks):
            for x in group:
                out[x.id] = x.model_dump(mode="json")
        return out

    a, b = index(old), index(new)
    return sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))


_BOXES: dict[tuple[str, int, str], tuple[float, float, float, float] | None] = {}
_BOX_LOCK = threading.Lock()


def with_citation_boxes(findings: list[Finding], tender_pdf: Path) -> list[Finding]:
    """The engine cites (page, verbatim quote) without a box; add pdfplumber's box (cached per quote)."""
    path = Path(tender_pdf)
    want = {(r.page, r.quote) for f in findings for r in f.tender_refs if r.bbox is None and r.quote}
    if not want or not path.exists():
        return findings
    with _BOX_LOCK:
        missing = [k for k in want if (str(path), *k) not in _BOXES]
        if missing:
            with PdfText(path) as pdf:
                for page, quote in missing:
                    in_range = 1 <= page <= pdf.page_count
                    _BOXES[(str(path), page, quote)] = pdf.find_bbox(page, quote) if in_range else None
        boxes = {k: _BOXES[(str(path), *k)] for k in want}

    def boxed(r: Citation) -> Citation:
        b = boxes.get((r.page, r.quote)) if r.bbox is None and r.quote else None
        return r.model_copy(update={"bbox": b}) if b else r

    return [f.model_copy(update={"tender_refs": [boxed(r) for r in f.tender_refs]}) for f in findings]


def run_revisions(store: Store, uid: str, rid: str) -> list[dict]:
    prefix = f"{rid}-r"
    revs = [d for d in store.list_docs(f"workspaces/{uid}/revisions") if d.get("id", "").startswith(prefix)]
    return sorted(revs, key=lambda d: int(d["id"][len(prefix):]))


def latest_revision(store: Store, uid: str, rid: str) -> dict | None:
    revs = run_revisions(store, uid, rid)
    return revs[-1] if revs else None
