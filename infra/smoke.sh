#!/usr/bin/env bash
# Production smoke test (WS4). Usage: infra/smoke.sh [BASE_URL]
set -euo pipefail
BASE="${1:-https://kirchhoff.web.app}"
P=ordinal-mep
fail() { echo "smoke FAIL: $*" >&2; exit 1; }
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

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
echo "smoke OK: $BASE"
