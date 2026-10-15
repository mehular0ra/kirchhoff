"""POST /api/asset/{pack} for the grid and solar packs (spec §10; P2 Task 17). The engine result plus the Asset agent's
choice, on the same pools as /api/what-if: the engine work on the engine pool, the agent call on the LLM pool."""
import logging
from concurrent.futures import TimeoutError as FuturesTimeout

from fastapi import APIRouter, Depends

from kirchhoff.agents.asset import run_asset_pack
from kirchhoff.agents.copilot import call_with_timeout
from kirchhoff.runs.deps import Deps

from .errors import err

log = logging.getLogger("kirchhoff.asset")
ASSET_TIMEOUT_S = 9.5
PACKS = ("grid", "solar")


def make_router(deps: Deps, current_uid) -> APIRouter:
    router = APIRouter()

    @router.post("/api/asset/{pack}")
    def asset(pack: str, uid: str = Depends(current_uid)):
        if pack not in PACKS or pack not in deps.asset_engines:
            return err(404, "unknown_pack")
        budget = ASSET_TIMEOUT_S  # read once: the agent gets what is left of this budget, not a fixed 5 s
        try:
            return call_with_timeout(lambda: run_asset_pack(deps, pack, budget), budget)
        except FuturesTimeout:
            return err(504, "timeout")
        except Exception as exc:  # the engine itself failed: not the caller's fault, and not an unhandled 500
            log.warning("asset engine failed for %s: %r", pack, exc)
            return err(502, "engine_failed")

    return router
