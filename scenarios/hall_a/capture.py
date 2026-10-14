"""Golden capture, step 1 (spec §11): export a completed, signed Hall B run from Firestore + Cloud Storage.
  cd services/api && GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep \
    uv run python ../../scenarios/hall_a/capture.py export --rid <run id> [--target hall-a|pune-edge-1] [--uid <uid>]
writes scenarios/demo_world/captures/{target}.json (uid anonymised). Step 2 is `make demo-world`: it rewrites each
capture into its signed static bundle (kirchhoff.enterprise.capture.to_static) and regenerates the demo world."""
import argparse
import json
import sys
from pathlib import Path

from kirchhoff.enterprise.capture import TARGETS, CaptureError, GcsReader, export_run, find_workspace_for_run

HERE = Path(__file__).resolve().parent
CAPTURES = HERE.parent / "demo_world" / "captures"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kirchhoff golden capture")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export", help="export a completed, signed Hall B run")
    ex.add_argument("--rid", required=True)
    ex.add_argument("--uid")
    ex.add_argument("--target", choices=sorted(TARGETS), default="hall-a")
    args = ap.parse_args(argv)

    from google.cloud import firestore

    from kirchhoff.store.firestore import FirestoreStore

    db = firestore.Client(project="ordinal-mep")
    try:
        uid = args.uid or find_workspace_for_run(db, args.rid)
        raw = export_run(FirestoreStore(db), GcsReader(), uid, args.rid)
    except CaptureError as exc:
        print(f"capture failed: {exc}", file=sys.stderr)
        return 1
    out = CAPTURES / f"{args.target}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(raw.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=1) + "\n",
                   encoding="utf-8")
    b = raw.bundle
    print(f"{out}: revisions={[r.id for r in b.revisions]} events={len(b.events)} prs={len(b.prs)} "
          f"option={b.runs[0].selected_option}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
