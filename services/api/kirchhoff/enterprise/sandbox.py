"""ERP/CRM sandbox (spec §9.5, §13.3) over the Store protocol. Seed data is read-only; each visitor's PRs and CRM
stage overlays live under sandbox_visitors/{uid} (ruling W1). Stock is never decremented. Sandbox (simulated)."""
import hashlib
import time
from typing import Callable

from kirchhoff.contracts import CrmOverlay, Material, Opportunity, PRLine, PurchaseRequisition
from kirchhoff.store import Store
from kirchhoff.store.validate import firestore_safe_problems

from .model import EnterpriseSeed, seed_hash

MATERIALS = "seed/erp/materials"
SEED_PRS = "seed/erp/prs"
OPPORTUNITIES = "seed/crm/opportunities"
SEED_META = "seed/meta"
COUNTERS = "sandbox_meta/counters"
FIRST_VISITOR_PR = 301
PR_STATUSES = ("draft", "submitted", "blocked")
STAGES = ("Qualification", "Proposal", "Negotiation", "Design in progress", "Design approved", "Closed won",
          "Closed lost")


class NotFound(KeyError):
    """Unknown PR or opportunity (HTTP 404)."""


def visitor_path(uid: str) -> str:
    if not uid or "/" in uid:
        raise ValueError("uid must be a non-empty string without '/'")
    return f"sandbox_visitors/{uid}"


def key_id(idempotency_key: str) -> str:
    """Idempotency keys contain ':' and vendor names; hash them into a valid document id."""
    return hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:40]


def _doc_id(value: str) -> str:
    if not value or "/" in value:
        raise NotFound(value)
    return value


class Sandbox:
    def __init__(self, store: Store, clock: Callable[[], float] = time.time) -> None:
        self.store = store
        self.clock = clock

    # ---- seed -------------------------------------------------------------------------------------------
    def load_seed(self, seed: EnterpriseSeed) -> dict[str, int]:
        items = [(f"{MATERIALS}/{m.id}", m.model_dump(mode="json")) for m in seed.materials]
        items += [(f"{SEED_PRS}/{p.id}", p.model_dump(mode="json")) for p in seed.prs]
        items += [(f"{OPPORTUNITIES}/{o.id}", o.model_dump(mode="json")) for o in seed.opportunities]
        problems = [f"{path}: {p}" for path, doc in items for p in firestore_safe_problems(doc)]
        if problems:
            raise ValueError("seed is not Firestore-safe: " + "; ".join(problems[:5]))
        self.store.delete_tree("seed/erp")
        self.store.delete_tree("seed/crm")
        self.store.batch_set(items)
        counts = {"materials": len(seed.materials), "prs": len(seed.prs), "opportunities": len(seed.opportunities)}
        self.store.set_doc(SEED_META, {**counts, "hash": seed_hash(seed), "accounts": list(seed.accounts),
                                       "notice": seed.notice, "label": seed.label})
        return counts

    def meta(self) -> dict:
        return self.store.get_doc(SEED_META) or {}

    # ---- ERP ----------------------------------------------------------------------------------------------
    def list_materials(self) -> list[Material]:
        return sorted((Material.model_validate(d) for d in self.store.list_docs(MATERIALS)), key=lambda m: m.id)

    def list_prs(self, uid: str | None) -> list[PurchaseRequisition]:
        prs = [PurchaseRequisition.model_validate(d) for d in self.store.list_docs(SEED_PRS)]
        if uid:
            prs += [PurchaseRequisition.model_validate(d) for d in self.store.list_docs(f"{visitor_path(uid)}/prs")]
        return sorted(prs, key=lambda p: (-p.created_at, p.id))

    def create_pr(self, uid: str, project_id: str, revision: str, lines: list[PRLine],
                  idempotency_key: str) -> PurchaseRequisition:
        base = visitor_path(uid)
        if not idempotency_key:
            raise ValueError("idempotency_key is required")
        if not lines:
            raise ValueError("a purchase requisition needs at least one line")
        key_doc = f"{base}/keys/{key_id(idempotency_key)}"
        out: dict = {}

        def fn(snap: dict) -> list:
            out.clear()  # Firestore may retry the transaction function
            known = snap.get(key_doc)
            if known is not None:
                out["existing"] = known["pr_id"]
                return []
            n = int((snap.get(COUNTERS) or {}).get("next_pr", FIRST_VISITOR_PR))
            pr = PurchaseRequisition(id=f"PR-2026-{n:04d}", project_id=project_id, revision=revision,
                                     lines=list(lines), status="submitted", created_at=self.clock())
            out["pr"] = pr
            return [(f"{base}/prs/{pr.id}", pr.model_dump(mode="json")),
                    (key_doc, {"pr_id": pr.id, "key": idempotency_key}),
                    (COUNTERS, {"next_pr": n + 1})]

        self.store.transact([key_doc, COUNTERS], fn)
        if "existing" in out:
            doc = self.store.get_doc(f"{base}/prs/{out['existing']}")
            if doc is None:
                raise NotFound(out["existing"])
            return PurchaseRequisition.model_validate(doc)
        return out["pr"]

    def set_pr_status(self, uid: str, pr_id: str, status: str) -> None:
        if status not in PR_STATUSES:
            raise ValueError(f"status must be one of {PR_STATUSES}")
        path = f"{visitor_path(uid)}/prs/{_doc_id(pr_id)}"

        def fn(snap: dict) -> list:
            doc = snap.get(path)
            if doc is None:
                raise NotFound(pr_id)
            return [(path, {**doc, "status": status})]

        self.store.transact([path], fn)

    # ---- CRM ----------------------------------------------------------------------------------------------
    def list_opportunities(self, uid: str | None) -> list[Opportunity]:
        opps = sorted((Opportunity.model_validate(d) for d in self.store.list_docs(OPPORTUNITIES)), key=lambda o: o.id)
        if not uid:
            return opps
        stages = {d["opportunity_id"]: d["stage"] for d in self.store.list_docs(f"{visitor_path(uid)}/crm")}
        return [o.model_copy(update={"stage": stages[o.id]}) if o.id in stages else o for o in opps]

    def set_opportunity_stage(self, uid: str, opportunity_id: str, stage: str) -> CrmOverlay:
        base = visitor_path(uid)
        if stage not in STAGES:
            raise ValueError(f"stage must be one of {STAGES}")
        if self.store.get_doc(f"{OPPORTUNITIES}/{_doc_id(opportunity_id)}") is None:
            raise NotFound(opportunity_id)
        ov = CrmOverlay(opportunity_id=opportunity_id, stage=stage, updated_at=self.clock())
        self.store.set_doc(f"{base}/crm/{opportunity_id}", ov.model_dump(mode="json"))
        return ov

    def reset_visitor(self, uid: str) -> int:
        return self.store.delete_tree(visitor_path(uid))
