"""POST /api/asset/{pack} for the grid and solar packs (spec §10; P2 Task 17). The engine result plus the Asset agent's
choice, on the same pools as /api/what-if: the engine work on the engine pool, the agent call on the LLM pool."""
from concurrent.futures import TimeoutError as FuturesTimeout

from fastapi import APIRouter, Depends

from kirchhoff.agents.asset import run_asset_pack
from kirchhoff.agents.copilot import call_with_timeout
from kirchhoff.runs.deps import Deps

from .errors import err

ASSET_TIMEOUT_S = 9.5
PACKS = ("grid", "solar")


def make_router(deps: Deps, current_uid) -> APIRouter:
    router = APIRouter()

    @router.post("/api/asset/{pack}")
    def asset(pack: str, uid: str = Depends(current_uid)):
        if pack not in PACKS or pack not in deps.asset_engines:
            return err(404, "unknown_pack")
        try:
            return call_with_timeout(lambda: run_asset_pack(deps, pack), ASSET_TIMEOUT_S)
        except FuturesTimeout:
            return err(504, "timeout")

    return router
