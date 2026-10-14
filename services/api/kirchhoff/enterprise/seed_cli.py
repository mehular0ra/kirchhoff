"""Load the generated enterprise seed into Firestore (seed/erp/**, seed/crm/**), the bids inbox (seed/inbox, spec §20)
and upload the demo documents to Cloud Storage seed/files/ (ruling W10). Run from services/api:
  GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep \
    uv run python -m kirchhoff.enterprise.seed_cli [--dry-run] [--docs ../../apps/web/public/demo/files]
"""
import argparse
import json
import sys
from pathlib import Path

from .model import load_enterprise_seed, seed_hash
from .paths import enterprise_seed_path
from .sandbox import Sandbox
from .world.inbox import inbox_seed_path, load_inbox, load_inbox_seed

BUCKET = "ordinal-mep.firebasestorage.app"
CONTENT_TYPES = {".pdf": "application/pdf", ".csv": "text/csv", ".json": "application/json"}


def upload_docs(files_dir: Path, bucket=None) -> list[str]:
    if bucket is None:
        from google.cloud import storage
        bucket = storage.Client(project="ordinal-mep").bucket(BUCKET)
    names = []
    for f in sorted(Path(files_dir).rglob("*")):
        if not f.is_file():
            continue
        blob = bucket.blob(f"seed/files/{f.relative_to(files_dir).as_posix()}")
        blob.cache_control = "public, max-age=300"
        blob.upload_from_filename(str(f), content_type=CONTENT_TYPES.get(f.suffix, "application/octet-stream"))
        names.append(blob.name)
    return names


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Load the Kirchhoff enterprise sandbox seed")
    ap.add_argument("--seed", type=Path, default=enterprise_seed_path())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--docs", type=Path)
    ap.add_argument("--inbox", type=Path, default=inbox_seed_path())
    args = ap.parse_args(argv)
    seed = load_enterprise_seed(args.seed)
    inbox = load_inbox_seed(args.inbox) if args.inbox.is_file() else None  # exists once build_inbox.py has run
    report: dict = {"seed": str(args.seed), "hash": seed_hash(seed), "materials": len(seed.materials),
                    "prs": len(seed.prs), "opportunities": len(seed.opportunities),
                    "inbox_emails": len(inbox.emails) if inbox else 0}
    if not args.dry_run:
        from kirchhoff.store.firestore import FirestoreStore
        store = FirestoreStore()
        report["written"] = Sandbox(store).load_seed(seed)
        if inbox is not None:
            report["inbox_written"] = load_inbox(store, inbox)
        if args.docs and args.docs.is_dir():  # documents exist from Task 11 on
            report["docs"] = upload_docs(args.docs)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
