#!/usr/bin/env bash
# Budget alert (spec §11): USD 200 equivalent on the INR billing account (ruling W12), alerts at 50 % and 90 %.
# Idempotent. Needs billing.budgets.create on billing account 012711-F23839-B5DB84.
# Usage: ALERT_EMAILS=<addr1,addr2,...> infra/budget_setup.sh   (addresses are never committed)
#        ALERT_EMAIL=<addr> infra/budget_setup.sh               (single address, back-compat)
set -euo pipefail
P=ordinal-mep
BA=012711-F23839-B5DB84
AMOUNT="${BUDGET_AMOUNT:-17600INR}"

IFS=',' read -ra RAW_EMAILS <<< "${ALERT_EMAILS:-${ALERT_EMAIL:?set ALERT_EMAILS (comma-separated) or ALERT_EMAIL to the team alert address(es)}}"
EMAILS=()
for addr in "${RAW_EMAILS[@]}"; do
  addr="${addr#"${addr%%[![:space:]]*}"}"  # trim leading whitespace
  addr="${addr%"${addr##*[![:space:]]}"}"  # trim trailing whitespace
  [ -n "$addr" ] && EMAILS+=("$addr")  # drop empty entries, e.g. from a trailing comma
done
if [ "${KIRCHHOFF_PARSE_ONLY:-0}" = "1" ]; then  # test hook: print the parsed addresses, never touch GCP
  printf '%s\n' "${EMAILS[@]}"
  exit 0
fi

gcloud services enable billingbudgets.googleapis.com --project=$P
EXISTING="$(gcloud billing budgets list --billing-account=$BA --billing-project=$P \
  --filter='displayName="kirchhoff-usd200"' --format='value(name)' | head -1)"
if [ -n "$EXISTING" ]; then
  echo "budget exists: $EXISTING"
  exit 0
fi

CHANNELS=()
for addr in "${EMAILS[@]}"; do
  ch="$(gcloud beta monitoring channels list --project=$P \
    --filter="type=\"email\" AND labels.email_address=\"$addr\"" --format='value(name)' | head -1)"
  if [ -n "$ch" ]; then CHANNELS+=("$ch"); fi
done
EXTRA=()
if [ "${#CHANNELS[@]}" -gt 0 ]; then
  CHANNELS_CSV="$(IFS=,; echo "${CHANNELS[*]}")"
  EXTRA+=(--notifications-rule-monitoring-notification-channels="$CHANNELS_CSV")
fi
gcloud billing budgets create --billing-account=$BA --billing-project=$P --display-name=kirchhoff-usd200 \
  --budget-amount="$AMOUNT" --filter-projects=projects/$P \
  --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 ${EXTRA[@]+"${EXTRA[@]}"}
echo "budget kirchhoff-usd200 created ($AMOUNT); alerts -> ${#CHANNELS[@]} channel(s)"
