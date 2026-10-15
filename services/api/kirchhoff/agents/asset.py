"""Asset agent (spec §10, §6.3): picks one engine option for the grid or solar pack and gives a reason in one sentence.
The engine does all the arithmetic. The agent may only choose one of the engine's option ids that passes its checks
(matched to the engine's own spelling); anything else keeps the engine's `recommended`. Its reason is sanitized with
the option ids and the finding element ids allowlisted, and a reason with a {slot} or a number in words is replaced,
so a quantity it invented never reaches the page."""
import json
import logging
import time

from pydantic import BaseModel

from .copilot import _LLM_POOL, call_with_timeout
from .prose_guard import prose_is_safe
from .runner import run_json
from .specs import ASSET
from .trust import sanitize

log = logging.getLogger("kirchhoff.asset")
AGENT_MARGIN_S = 0.25  # what the route keeps of its budget to answer after the agent
MIN_AGENT_S = 0.05


class AssetChoice(BaseModel):
    option: str
    reason: str = ""


def _dump(f):
    return f.model_dump(mode="json") if hasattr(f, "model_dump") else f


def run_asset_pack(deps, pack: str, budget_s: float | None = None) -> dict:
    """The engine result for `pack` plus `findings` serialized and `choice = {option, reason, source}`. Runs on the
    engine pool (the route); the agent call goes to the LLM pool so the two never wait on each other. `budget_s` is
    the route's whole budget: the agent gets at most what is left of it (minus a margin), so a finished engine result
    is never lost because the agent was slow."""
    started = time.monotonic()
    result = deps.asset_engines[pack](deps.scenarios_dir / pack)
    options = result.get("options", [])
    ids = [str(o.get("id")) for o in options]
    # An option the engine marks as failing its checks can never be "Recommended" (the page would show a Fail tag
    # next to it while the Checker shows another option's findings); options without a `passes` flag are allowed.
    pickable = {str(o.get("id")).casefold(): str(o.get("id")) for o in options if o.get("passes") is not False}
    findings = [_dump(f) for f in result.get("findings", [])]
    rec = result.get("recommended")
    choice = {"option": rec, "reason": f"Kept the engine recommendation {rec}.", "source": "engine"}
    agent_s = ASSET.timeout_s
    if budget_s is not None:
        agent_s = min(agent_s, budget_s - (time.monotonic() - started) - AGENT_MARGIN_S)
    if agent_s <= MIN_AGENT_S:
        log.warning("asset agent skipped for %s: no time left in the route budget", pack)
        return {**result, "findings": findings, "choice": choice}
    msg = (f"Asset pack: {pack}. Engine options (JSON): {json.dumps(options, default=str)[:6000]}. "
           f"Engine recommendation: {rec}. Choose one option id whose \"passes\" is not false. "
           'Reply with JSON {"option": id, "reason": one sentence}.')
    try:
        reply = call_with_timeout(lambda: run_json(deps.runner, ASSET, pack, msg, AssetChoice)[0], agent_s,
                                  pool=_LLM_POOL)
        picked = pickable.get(reply.option.strip().casefold())  # the engine's own spelling, a passing option only
        if picked is not None:
            allowed = set(ids) | {f.get("element_id") for f in findings if f.get("element_id")}
            template = f"Recommended {picked} on the engine's ranking."
            reason = sanitize(reply.reason, allowed, template) if prose_is_safe(reply.reason) else template
            choice = {"option": picked, "source": "agent", "reason": reason}
    except Exception as exc:  # timeout, agent error, bad JSON: the engine's recommendation stands
        log.warning("asset agent fallback for %s: %r", pack, exc)
    return {**result, "findings": findings, "choice": choice}
