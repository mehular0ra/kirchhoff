"""Precompute the triage of every seeded email with the real Inbox agent (spec §20 "static first"; ruling B5).
Run once at golden-capture time, from services/api:
  GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep \
    GOOGLE_CLOUD_LOCATION=global uv run python -m kirchhoff.inbox.precompute --backend adk
then `make demo-world` folds scenarios/demo_world/captures/inbox-triage.json into /demo/inbox.json and the seed.
--backend is required. `--backend replay --out <file>` runs the FAKE_REPLIES fixtures instead (no cloud access); it
refuses the default --out so that hand-authored replies never reach the static bundle as the real model's output."""
import argparse
import dataclasses
import json
import sys
from pathlib import Path

from kirchhoff.agents.ports import ErpSnapshot
from kirchhoff.agents.runner import MODEL, AgentRunner, ReplayRunner
from kirchhoff.agents.specs import INBOX
from kirchhoff.contracts import Opportunity
from kirchhoff.enterprise.world.inbox import CAPTURE_VERSION, InboxSeed, load_inbox_seed

from .fit import SupplyFn, day_zero_supply
from .triage import triage_email

OFFLINE_TIMEOUT_S = 60.0  # no request budget offline; the live endpoint keeps INBOX.timeout_s


def precompute(seed: InboxSeed, *, runner: AgentRunner, scenarios_dir: Path, opportunities: list[Opportunity], erp,
               supply_fn: SupplyFn = day_zero_supply) -> dict:
    spec = dataclasses.replace(INBOX, timeout_s=OFFLINE_TIMEOUT_S)
    results = {e.id: triage_email(e, runner=runner, scenarios_dir=scenarios_dir, opportunities=opportunities, erp=erp,
                                  appetite=seed.appetite, as_of=seed.as_of, source="precomputed", now=seed.as_of,
                                  supply_fn=supply_fn, spec=spec).model_dump(mode="json")
               for e in sorted(seed.emails, key=lambda m: m.id)}
    return {"version": CAPTURE_VERSION, "model": MODEL, "as_of": seed.as_of, "results": results}


def _runner(backend: str) -> AgentRunner:
    if backend == "replay":
        from kirchhoff.runs.fakes import FAKE_REPLIES
        return ReplayRunner(FAKE_REPLIES)
    if backend == "genai":
        from kirchhoff.agents.genai_runner import GenaiRunner
        return GenaiRunner()
    from kirchhoff.agents.adk_runner import AdkRunner
    return AdkRunner()


def main(argv: list[str] | None = None) -> int:
    from kirchhoff.api.deps import scenarios_dir
    from kirchhoff.enterprise.client import make_enterprise_client

    scen = scenarios_dir()
    ap = argparse.ArgumentParser(description="Precompute the bids inbox triage with the real Inbox agent")
    default_out = scen / "demo_world" / "captures" / "inbox-triage.json"
    ap.add_argument("--seed", type=Path, default=scen / "demo_world" / "out" / "inbox_seed.json")
    ap.add_argument("--out", type=Path, default=None, help=f"default: {default_out} (not allowed with --backend replay)")
    ap.add_argument("--backend", choices=("adk", "genai", "replay"), required=True)  # never a silent default
    args = ap.parse_args(argv)
    if args.backend == "replay" and args.out is None:
        # `make demo-world` folds the default capture into the static bundle: hand-authored replies must not land
        # there labelled with the real model.
        print("precompute: --backend replay needs an explicit --out (it never writes the default capture)",
              file=sys.stderr)
        return 2
    args.out = args.out or default_out
    enterprise = make_enterprise_client()
    try:
        capture = precompute(load_inbox_seed(args.seed), runner=_runner(args.backend), scenarios_dir=scen,
                             opportunities=enterprise.list_opportunities(None),
                             erp=ErpSnapshot(enterprise.list_materials()))
    except Exception as exc:  # never write a partial capture
        print(f"precompute failed, nothing written: {exc!r}", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(capture, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    for eid, r in sorted(capture["results"].items()):
        print(f"{eid}: {r['fit']['verdict'] or 'not a bid'} ({r['quotes_verified']}/{r['quotes_total']} quotes verified)")
    print(f"wrote {args.out}; run `make demo-world` to fold it into the static bundle")
    return 0


if __name__ == "__main__":
    sys.exit(main())
