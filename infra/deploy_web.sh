#!/usr/bin/env bash
# Build the web app and deploy Hosting + Firestore/Storage rules. Always deploy through this script:
# infra/public_dist is a symlink to apps/web/dist because firebase-tools rejects public dirs outside infra/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO="$ROOT/apps/web/public/demo"
for f in world.json integrations.json projects/hall-a.json; do
  [ -f "$DEMO/$f" ] || echo "deploy_web: warning: apps/web/public/demo/$f is missing (Task 11 generates it)" >&2
done
(cd "$ROOT/apps/web" && npm run build)
cd "$ROOT/infra"
npx -y firebase-tools@latest deploy --project ordinal-mep --only hosting:kirchhoff,firestore:rules,storage --non-interactive
