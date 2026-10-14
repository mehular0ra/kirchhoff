#!/usr/bin/env bash
# Build the web app and deploy Hosting + Firestore/Storage rules. Always deploy through this script:
# infra/public_dist is a symlink to apps/web/dist because firebase-tools rejects public dirs outside infra/.
# ALLOW_NO_DEMO=1 skips the demo-world gate (never for a judged deploy).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO="$ROOT/apps/web/public/demo"
if [ "${ALLOW_NO_DEMO:-0}" != "1" ]; then
  missing=()
  for f in world.json integrations.json projects/hall-a.json; do [ -f "$DEMO/$f" ] || missing+=("$f"); done
  if ((${#missing[@]})); then
    echo "deploy_web: missing demo files: ${missing[*]} (run make demo-world)" >&2
    exit 1
  fi
  (cd "$ROOT/services/api" && uv run python ../../scenarios/demo_world/build.py --check) || {
    echo "deploy_web: the committed demo world is stale; run make demo-world and commit it" >&2
    exit 1
  }
fi
(cd "$ROOT/apps/web" && npm run build)
[ -f "$ROOT/apps/web/dist/demo/docs/tender-hall-a.pdf" ] || {
  echo "deploy_web: dist/demo/docs/tender-hall-a.pdf is missing (WS2 renders scenarios/hall_a/out; WS3's prebuild copies it)" >&2
  exit 1
}
cd "$ROOT/infra"
npx -y firebase-tools@latest deploy --project ordinal-mep --only hosting:kirchhoff,firestore:rules,storage --non-interactive
