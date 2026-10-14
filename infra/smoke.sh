#!/usr/bin/env bash
# Production smoke test (WS4). Usage: infra/smoke.sh [BASE_URL]
set -euo pipefail
BASE="${1:-https://kirchhoff.web.app}"
P=ordinal-mep
fail() { echo "smoke FAIL: $*" >&2; exit 1; }
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
header() { curl -fsSI "$BASE$2" | tr -d '\r' | awk -v h="$1:" 'tolower($1)==h { sub(/^[^:]*: */, ""); print; exit }'; }
cc() { header cache-control "$1"; }

curl -fsS "$BASE/api/health" | grep -q '"ok":true' || fail "/api/health is not ok"
[ "$(code "$BASE/api/whoami")" = "401" ] || fail "GET /api/whoami without a token must be 401"
[ "$(code "$BASE/api/enterprise/erp/materials")" = "401" ] || fail "the enterprise proxy without a token must be 401"
case "$BASE" in  # a local `make dev-api` (P2 Task 18) has no Hosting: API checks only
  http://localhost*|http://127.0.0.1*) echo "smoke OK (API only): $BASE"; exit 0 ;;
esac
curl -fsS "$BASE/" | grep -qi '<div id="root">' || fail "SPA shell missing"
ENT_URL="$(gcloud run services describe kirchhoff-enterprise --project=$P --region=asia-south1 \
  --format='value(status.url)' 2>/dev/null || true)"
if [ -n "$ENT_URL" ]; then
  [ "$(code "$ENT_URL/health")" = "403" ] || fail "kirchhoff-enterprise must reject unauthenticated callers (403)"
fi

for path in / /app /app/p/hall-a /index.html; do
  [ "$(cc "$path")" = "no-cache" ] || fail "Cache-Control on $path is '$(cc "$path")' (want no-cache)"
done
[ "$(cc "/api/health")" != "no-cache" ] || fail "Cache-Control on /api/health must NOT be no-cache (got: $(cc "/api/health"))"
ASSET="$(curl -fsS "$BASE/" | grep -oE '/assets/[^"]+\.js' | head -1)"
[ -n "$ASSET" ] || fail "index.html references no /assets/*.js"
[ "$(cc "$ASSET")" = "public, max-age=31536000, immutable" ] || fail "Cache-Control on $ASSET is '$(cc "$ASSET")'"

[ "$(cc /demo/world.json)" = "public, max-age=300" ] || fail "Cache-Control on /demo/world.json is '$(cc /demo/world.json)'"
curl -fsS "$BASE/demo/projects/hall-a.json" | python3 -c 'import json, sys
b = json.load(sys.stdin)
assert b["project"]["id"] == "hall-a" and b["approvals"] and all(r["model"] for r in b["revisions"])' \
  || fail "/demo/projects/hall-a.json is not the signed Hall A bundle"
for doc in /demo/docs/tender-hall-a.pdf /demo/files/hall-a/calc-report.pdf; do
  case "$(header content-type "$doc")" in
    application/pdf*) ;;
    *) fail "$doc is not served as a PDF (the SPA fallback answered?)" ;;
  esac
done
echo "smoke OK: $BASE"
