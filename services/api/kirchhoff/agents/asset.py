"""Asset agent (spec §10, §6.3): picks one engine option for the grid or solar pack and gives a reason in one sentence.
The engine does all the arithmetic. The agent may only choose one of the engine's option ids (matched to the engine's
own spelling); anything else keeps the engine's `recommended`. Its reason is sanitized with only the option ids and
the finding element ids allowlisted, so a digit it invented never reaches the page."""
import json
import logging

from pydantic import BaseModel

from .copilot import _LLM_POOL, call_with_timeout
from .runner import run_json
from .specs import ASSET
from .trust import sanitize

log = logging.getLogger("kirchhoff.asset")


class AssetChoice(BaseModel):
    option: str
    reason: str = ""


def _dump(f):
    return f.model_dump(mode="json") if hasattr(f, "model_dump") else f


def run_asset_pack(deps, pack: str) -> dict:
    """The engine result for `pack` plus `findings` serialized and `choice = {option, reason, source}`. Runs on the
    engine pool (the route); the agent call goes to the LLM pool so the two never wait on each other."""
    result = deps.asset_engines[pack](deps.scenarios_dir / pack)
    options = result.get("options", [])
    ids = [str(o.get("id")) for o in options]
    findings = [_dump(f) for f in result.get("findings", [])]
    rec = result.get("recommended")
    choice = {"option": rec, "reason": f"Kept the engine recommendation {rec}.", "source": "engine"}
    msg = (f"Asset pack: {pack}. Engine options (JSON): {json.dumps(options, default=str)[:6000]}. "
           f"Engine recommendation: {rec}. Choose one option id. "
           'Reply with JSON {"option": id, "reason": one sentence}.')
    try:
        reply = call_with_timeout(lambda: run_json(deps.runner, ASSET, pack, msg, AssetChoice)[0], ASSET.timeout_s,
                                  pool=_LLM_POOL)
        picked = {i.casefold(): i for i in ids}.get(reply.option.strip().casefold())  # the engine's own spelling
        if picked is not None:
            allowed = set(ids) | {f.get("element_id") for f in findings if f.get("element_id")}
            choice = {"option": picked, "source": "agent",
                      "reason": sanitize(reply.reason, allowed, f"Recommended {picked} on the engine's ranking.")}
    except Exception as exc:  # timeout, agent error, bad JSON: the engine's recommendation stands
        log.warning("asset agent fallback for %s: %r", pack, exc)
    return {**result, "findings": findings, "choice": choice}
