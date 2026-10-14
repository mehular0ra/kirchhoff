#!/usr/bin/env bash
# Uptime checks on / and /api/health with email alerts (spec §11). Idempotent.
# Usage: ALERT_EMAILS=<addr1,addr2,...> infra/monitoring_setup.sh   (addresses are never committed)
#        ALERT_EMAIL=<addr> infra/monitoring_setup.sh               (single address, back-compat)
set -euo pipefail
P=ordinal-mep
HOST=kirchhoff.web.app

IFS=',' read -ra EMAILS <<< "${ALERT_EMAILS:-${ALERT_EMAIL:?set ALERT_EMAILS (comma-separated) or ALERT_EMAIL to the team alert address(es)}}"

ensure_channel() {  # email address, display index -> channel resource name, idempotent on the email_address label
  local addr="$1" idx="$2" existing
  existing="$(gcloud beta monitoring channels list --project=$P \
    --filter="type=\"email\" AND labels.email_address=\"$addr\"" --format='value(name)' | head -1)"
  if [ -z "$existing" ]; then
    existing="$(gcloud beta monitoring channels create --project=$P --type=email \
      --display-name="Kirchhoff alerts ($idx)" --channel-labels=email_address="$addr" --format='value(name)')"
  fi
  echo "$existing"
}
CHANNELS=()
idx=1
for addr in "${EMAILS[@]}"; do
  CHANNELS+=("$(ensure_channel "$addr" "$idx")")
  idx=$((idx + 1))
done
CHANNELS_JSON="$(printf '"%s",' "${CHANNELS[@]}")"
CHANNELS_JSON="[${CHANNELS_JSON%,}]"

check_id() {  # display name -> uptime check id, or "" when absent
  gcloud monitoring uptime list-configs --project=$P --filter="displayName=\"$1\"" --format='value(name)' \
    | head -1 | sed 's#.*/##'
}
ensure_check() {  # display name, path, content matcher
  if [ -z "$(check_id "$1")" ]; then
    gcloud monitoring uptime create "$1" --project=$P --resource-type=uptime-url \
      --resource-labels=host=$HOST,project_id=$P --protocol=https --port=443 --path="$2" \
      --period=5 --timeout=10 --matcher-type=contains-string --matcher-content="$3" >/dev/null
  fi
  check_id "$1"
}
WEB_ID="$(ensure_check kirchhoff-web / 'id="root"')"
API_ID="$(ensure_check kirchhoff-api-health /api/health '"ok":true')"

ensure_policy() {  # display name, uptime check id
  if [ -n "$(gcloud monitoring policies list --project=$P --filter="displayName=\"$1\"" --format='value(name)' | head -1)" ]; then
    return 0
  fi
  local f
  f="$(mktemp)"
  cat > "$f" <<JSON
{
  "displayName": "$1",
  "combiner": "OR",
  "conditions": [{
    "displayName": "$1: uptime check failing",
    "conditionThreshold": {
      "filter": "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.label.check_id=\"$2\" AND resource.type=\"uptime_url\"",
      "aggregations": [{"alignmentPeriod": "1200s", "perSeriesAligner": "ALIGN_NEXT_OLDER",
                        "crossSeriesReducer": "REDUCE_COUNT_FALSE", "groupByFields": ["resource.label.*"]}],
      "comparison": "COMPARISON_GT", "thresholdValue": 1, "duration": "300s", "trigger": {"count": 1}
    }
  }],
  "notificationChannels": $CHANNELS_JSON
}
JSON
  gcloud monitoring policies create --project=$P --policy-from-file="$f" >/dev/null
  rm -f "$f"
}
ensure_policy "Kirchhoff web down" "$WEB_ID"
ensure_policy "Kirchhoff API health down" "$API_ID"
echo "uptime checks: kirchhoff-web=$WEB_ID kirchhoff-api-health=$API_ID; alerts -> ${#CHANNELS[@]} channel(s)"
