"""Build the bids inbox (spec §20): apps/web/public/demo/inbox.json + rendered attachments (static bundle) and
scenarios/demo_world/out/inbox_seed.json + the same attachments (API image, Firestore seed). Run from services/api:
  uv run python ../../scenarios/demo_world/build_inbox.py            # write the files
  uv run python ../../scenarios/demo_world/build_inbox.py --check    # exit 1 if the committed files are stale
captures/inbox-triage.json (WS2 `python -m kirchhoff.inbox.precompute`, golden-capture time) is folded in if present."""
import argparse
import sys
from pathlib import Path

from kirchhoff.enterprise.world.config import load_world_config
from kirchhoff.enterprise.world.inbox import (TRIAGE_CAPTURE, build_inbox, inbox_diff_on_disk, load_triage_capture,
                                              write_inbox)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the Kirchhoff bids inbox")
    ap.add_argument("--check", action="store_true", help="fail if the files on disk differ from a fresh build")
    args = ap.parse_args(argv)
    cfg = load_world_config(HERE / "world.yaml")
    triage = load_triage_capture(ROOT / TRIAGE_CAPTURE)
    build = build_inbox(cfg, ROOT / "scenarios", triage)
    if build_inbox(cfg, ROOT / "scenarios", triage).digest() != build.digest():
        print("build_inbox: two builds differ; the generator is not deterministic", file=sys.stderr)
        return 1
    if args.check:
        stale = inbox_diff_on_disk(build, ROOT)
        if stale:
            print("stale inbox files: " + ", ".join(stale), file=sys.stderr)
            return 1
        print(f"inbox up to date ({build.digest()[:16]})")
        return 0
    written = write_inbox(build, ROOT)
    print(f"inbox {build.digest()[:16]}: {len(build.seed.emails)} emails, {len(written)} files; "
          f"triaged {sorted(triage)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
