#!/usr/bin/env bash
# Firebase App Check (spec §1, §7; rulings W13, W19; P4 Task 15). Usage:
#   infra/appcheck.sh debug-token                 create or reuse the Playwright debug token (Secret Manager) and register it
#   infra/appcheck.sh status                      enforcement mode of Firestore, Cloud Storage and Firebase AI Logic
#   APPCHECK_ENFORCE_CONFIRM=yes infra/appcheck.sh enforce [service...]
#                                                 switch to ENFORCED (all three by default, or just the services named)
#   infra/appcheck.sh unenforce [service...]      the rollback: back to UNENFORCED, no confirmation needed
# Enforcing locks out every client that has no App Check token. Run it only after Mehul's "go" on issue #15 and the
# first deploy plus a green e2e with the debug token. The debug-token value lives only in Secret Manager: it is sent to
# the API on stdin and never printed or placed on a command line.
set -euo pipefail
P=ordinal-mep
APP_ID="1:1015632998221:web:c98110f2fc88424da81104"
SECRET=kirchhoff-e2e-appcheck-debug-token
API="https://firebaseappcheck.googleapis.com/v1/projects/$P"
SERVICES=(firestore.googleapis.com firebasestorage.googleapis.com firebaseml.googleapis.com)

# Test safety hook (incident of 15 Oct 2026: a test run with stubs that were not executable fell through to the REAL gcloud
# and curl and enforced App Check on ordinal-mep). With APPCHECK_FAKE_DIR set, gcloud, curl and python3 come from that
# directory ONLY, never from PATH, and a stub that is missing or not executable stops the script. Under pytest without it
# the script refuses to run at all. Nobody sets either in real use.
if [ -n "${APPCHECK_FAKE_DIR:-}" ]; then
  for tool in curl python3 gcloud; do  # (keep this order: test_infra_scripts scans the text of this file)
    [ -x "$APPCHECK_FAKE_DIR/$tool" ] || {
      echo "appcheck: stub $tool is missing or not executable in $APPCHECK_FAKE_DIR" >&2
      exit 4
    }
    eval "$tool() { \"\$APPCHECK_FAKE_DIR/$tool\" \"\$@\"; }"
  done
elif [ -n "${PYTEST_CURRENT_TEST:-}" ]; then
  echo "appcheck: refusing to run under pytest against the real project (use the stubs and APPCHECK_FAKE_DIR)" >&2
  exit 3
fi

call() {  # method url [json body: sent on stdin so a token never appears in a process listing]
  local auth
  auth="$(gcloud auth print-access-token)"
  if [ -n "${3:-}" ]; then
    printf '%s' "$3" | curl -fsS -X "$1" -H "Authorization: Bearer $auth" -H "x-goog-user-project: $P" \
      -H "Content-Type: application/json" "$2" -d @-
  else
    curl -fsS -X "$1" -H "Authorization: Bearer $auth" -H "x-goog-user-project: $P" "$2"
  fi
}

case "${1:-}" in
  debug-token)
    gcloud services enable secretmanager.googleapis.com firebaseappcheck.googleapis.com --project=$P
    if ! gcloud secrets describe $SECRET --project=$P >/dev/null 2>&1; then
      python3 -c 'import uuid; print(uuid.uuid4(), end="")' \
        | gcloud secrets create $SECRET --project=$P --replication-policy=automatic --data-file=-
    fi
    VALUE="$(gcloud secrets versions access latest --secret=$SECRET --project=$P)"
    REGISTERED="$(call GET "$API/apps/$APP_ID/debugTokens" | python3 -c 'import json, sys
print(any(t.get("displayName") == "playwright-e2e" for t in json.load(sys.stdin).get("debugTokens", [])))')"
    if [ "$REGISTERED" = "True" ]; then
      echo "debug token playwright-e2e already registered"
    else
      call POST "$API/apps/$APP_ID/debugTokens" "{\"displayName\": \"playwright-e2e\", \"token\": \"$VALUE\"}" >/dev/null
      echo "debug token playwright-e2e registered (value only in Secret Manager: $SECRET)"
    fi
    ;;
  status)
    for s in "${SERVICES[@]}"; do
      printf '%s ' "$s"
      call GET "$API/services/$s" | python3 -c 'import json, sys; print(json.load(sys.stdin).get("enforcementMode", "OFF"))'
    done
    ;;
  enforce|unenforce)
    cmd="$1"
    shift
    chosen=("$@")
    if [ ${#chosen[@]} -eq 0 ]; then chosen=("${SERVICES[@]}"); fi
    for s in "${chosen[@]}"; do
      case " ${SERVICES[*]} " in
        *" $s "*) ;;
        *) echo "unknown service: $s (known: ${SERVICES[*]})" >&2; exit 2 ;;
      esac
    done
    MODE=UNENFORCED
    if [ "$cmd" = enforce ]; then
      MODE=ENFORCED
      if [ "${APPCHECK_ENFORCE_CONFIRM:-}" != yes ]; then
        echo "refusing to enforce: this locks out every client without an App Check token." >&2
        echo "Check '$0 status', confirm Mehul's go on issue #15, then re-run with APPCHECK_ENFORCE_CONFIRM=yes." >&2
        exit 1
      fi
    fi
    for s in "${chosen[@]}"; do
      call PATCH "$API/services/$s?updateMask=enforcementMode" "{\"enforcementMode\": \"$MODE\"}" >/dev/null
    done
    bash "$0" status
    ;;
  *)
    echo "usage: $0 debug-token|status|enforce [service...]|unenforce [service...]" >&2
    exit 2
    ;;
esac
