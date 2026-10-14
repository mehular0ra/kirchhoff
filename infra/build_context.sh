#!/usr/bin/env bash
# Stage the Cloud Run build context: services/api (no .venv/tests/caches) + repo scenarios/ + static seed bundles.
# Usage: infra/build_context.sh OUT_DIR      (ALLOW_PARTIAL=1 tolerates missing scenario files)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:?usage: build_context.sh OUT_DIR}"
rm -rf "$OUT"
mkdir -p "$OUT/seed"
rsync -a --exclude='.venv/' --exclude='build/' --exclude='.pytest_cache/' --exclude='tests/' \
  --exclude='__pycache__/' --exclude='*.pyc' "$ROOT/services/api/" "$OUT/"
rsync -a --exclude='__pycache__/' --exclude='*.pyc' "$ROOT/scenarios/" "$OUT/scenarios/"
shopt -s nullglob
bundles=("$ROOT"/apps/web/public/demo/projects/*.json)
if ((${#bundles[@]})); then
  cp "${bundles[@]}" "$OUT/seed/"
else
  echo "build_context: no seed bundles yet in apps/web/public/demo/projects (seed: what-ifs return 404)" >&2
fi
for f in Dockerfile uv.lock pyproject.toml kirchhoff/api/app.py; do
  [ -e "$OUT/$f" ] || { echo "build_context: missing $f" >&2; exit 1; }
done
if [ ! -f "$OUT/scenarios/hall_a/tender.yaml" ] && [ "${ALLOW_PARTIAL:-0}" != "1" ]; then
  echo "build_context: scenarios/hall_a/tender.yaml missing (WS1); set ALLOW_PARTIAL=1 to build anyway" >&2
  exit 1
fi
echo "$OUT"
