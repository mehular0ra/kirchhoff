#!/usr/bin/env bash
set -euo pipefail
BASE=${1:-https://kirchhoff.web.app}
curl -fsS "$BASE/api/health" | grep -q '"ok":true'
curl -fsS "$BASE/" | grep -qi '<div id="root">'
code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/whoami")
[ "$code" = "401" ]
echo "smoke OK: $BASE"
