"""Bids inbox endpoints (spec §20; addendum Task I-2). GET merges the seed with the visitor's overlay. Triage runs
live only for the Hall B email (others answer 409 "precomputed"). Pursue creates the project and sets the CRM
opportunity to "Qualification" through the enterprise port (rulings B3, B4)."""
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout

from fastapi import APIRouter, Depends

from kirchhoff.agents.copilot import call_with_timeout
from kirchhoff.agents.ports import STAGE_QUALIFYING
from kirchhoff.contracts import Opportunity, Project
from kirchhoff.inbox import fit
from kirchhoff.inbox.models import PursueResult, TriageResult
from kirchhoff.inbox.store import inbox_view, load_seed, overlay_path, overlays, project_path
from kirchhoff.inbox.triage import triage_email
from kirchhoff.runs.deps import Deps

from .errors import err

log = logging.getLogger("kirchhoff.inbox")
TRIAGE_TIMEOUT_S = 9.5
TRIAGES_PER_HOUR = 10
KEEP_STAGES = ("Design approved", "Closed won", "Closed lost")  # Pursue never reopens these (ruling B3)
PACKS = ("datahall", "grid", "solar")
SUPPLY_FN = fit.day_zero_supply  # module attribute so tests can swap it
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="inbox")


def make_router(deps: Deps, current_uid) -> APIRouter:
    router = APIRouter()
    if os.environ.get("K_SERVICE"):  # on Cloud Run: warm the engine before the first triage (ruling B8)
        threading.Thread(target=fit.warm_engine, daemon=True).start()

    def seed_and_email(email_id: str | None = None):
        try:
            seed = load_seed(deps.store, deps.scenarios_dir)
        except (OSError, ValueError) as exc:
            log.warning("inbox seed unavailable: %r", exc)
            return None, None, err(503, "inbox_unavailable")
        email = next((e for e in seed.emails if e.id == email_id), None)
        if email_id is not None and email is None:
            return seed, None, err(404, "email_not_found")
        return seed, email, None

    @router.get("/api/inbox")
    def get_inbox(uid: str = Depends(current_uid)):
        seed, _, error = seed_and_email()
        return error or inbox_view(seed, overlays(deps.store, uid))

    @router.post("/api/inbox/{email_id}/triage")
    def triage(email_id: str, uid: str = Depends(current_uid)):
        seed, email, error = seed_and_email(email_id)
        if error:
            return error
        if not email.live_triage:
            return err(409, "precomputed")
        now, ws_path = deps.clock(), f"workspaces/{uid}"
        recent = [t for t in (deps.store.get_doc(ws_path) or {}).get("triage_starts", []) if now - t < 3600]
        if len(recent) >= TRIAGES_PER_HOUR:
            return err(429, "triage_rate_limit")
        deps.store.update_doc(ws_path, {"triage_starts": recent + [now]})

        def run() -> TriageResult:
            return triage_email(email, runner=deps.runner, scenarios_dir=deps.scenarios_dir,
                                opportunities=deps.enterprise.list_opportunities(uid), erp=deps.erp(),
                                appetite=seed.appetite, as_of=seed.as_of, source="live", now=now,
                                supply_fn=SUPPLY_FN)

        try:
            result = call_with_timeout(run, TRIAGE_TIMEOUT_S, pool=_POOL)  # cancels the future on timeout
        except FuturesTimeout:
            return err(504, "timeout")
        except Exception as exc:  # agent, repair or enterprise failure: the UI falls back to the recorded triage
            log.warning("live triage failed for %s: %r", email_id, exc)
            return err(502, "triage_failed")
        prev = deps.store.get_doc(overlay_path(uid, email_id)) or {}
        deps.store.set_doc(overlay_path(uid, email_id), {
            "email_id": email_id, "status": "pursued" if prev.get("status") == "pursued" else "triaged",
            "triage": result.model_dump(mode="json"), "pursue": prev.get("pursue"), "updated_at": now})
        return result.model_dump(mode="json")

    @router.post("/api/inbox/{email_id}/pursue")
    def pursue(email_id: str, uid: str = Depends(current_uid)):
        seed, email, error = seed_and_email(email_id)
        if error:
            return error
        prev = deps.store.get_doc(overlay_path(uid, email_id)) or {}
        if prev.get("pursue"):
            return prev["pursue"]  # idempotent
        raw = prev.get("triage") or email.triage
        if raw is None:
            return err(409, "not_triaged")
        t = TriageResult.model_validate(raw)
        asset = next((f for f in t.fields if f.key == "asset_type" and f.verification == "verified"), None)
        pack = asset.value if asset is not None and asset.value in PACKS else None
        if t.fit.verdict not in ("pursue", "clarify") or pack is None:
            return err(409, "cannot_pursue")
        now = deps.clock()
        try:
            current = {o.id: o for o in deps.enterprise.list_opportunities(uid)}
            opp = current.get(t.crm.opportunity_id or "")
            if opp is not None:
                previous, created = opp.stage, False
                stage = (previous if previous in KEEP_STAGES
                         else deps.enterprise.set_opportunity_stage(uid, opp.id, STAGE_QUALIFYING).stage)
            else:
                opp = deps.enterprise.create_opportunity(uid, Opportunity(
                    id=f"opp-{email.id}", account=t.crm.account or email.from_org,
                    name=t.crm.proposed_name or email.subject, stage=STAGE_QUALIFYING, value=0.0,
                    next_step="Qualify the bid from the bids inbox"))
                previous, created, stage = None, True, opp.stage
        except Exception as exc:
            log.warning("pursue %s: enterprise call failed: %r", email_id, exc)
            return err(502, "enterprise_unavailable")
        if email.project_id:  # an existing world project (Hall B): open its intake flow (ruling B4)
            project_id, project_name, project_created, open_ = email.project_id, None, False, f"/app/p/{email.project_id}"
        else:
            project_id = "bid-" + re.sub(r"^em-", "", email.id)
            project_name, project_created, open_ = f"{opp.account} · {opp.name}", True, None
            deps.store.set_doc(project_path(uid, project_id), Project(
                id=project_id, name=project_name, client=opp.account, asset_pack=pack, state="draft", sample=False,
                updated_at=now).model_dump(mode="json"))
        result = PursueResult(email_id=email_id, project_id=project_id, project_name=project_name,
                              project_created=project_created, opportunity_id=opp.id, opportunity_name=opp.name,
                              stage=stage, previous_stage=previous, opportunity_created=created,
                              open=open_).model_dump(mode="json")
        deps.store.set_doc(overlay_path(uid, email_id), {"email_id": email_id, "status": "pursued",
                                                         "triage": prev.get("triage"), "pursue": result,
                                                         "updated_at": now})
        return result

    return router
