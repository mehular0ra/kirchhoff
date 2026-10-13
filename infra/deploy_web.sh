#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
(cd "$ROOT/apps/web" && npm run build)
cd "$ROOT/infra"
npx -y firebase-tools@latest deploy --project ordinal-mep --only hosting:kirchhoff,firestore:rules,storage --non-interactive
