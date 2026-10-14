#!/usr/bin/env bash
# Build one image from the staged context and deploy it to kirchhoff-enterprise and kirchhoff-api (rulings W2, W3).
# Usage: infra/deploy_api.sh          FORCE=1 skips the live-run guard (never during judging).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
P=ordinal-mep
R=asia-south1
SA="kirchhoff-runtime@${P}.iam.gserviceaccount.com"
IMAGE="${R}-docker.pkg.dev/${P}/cloud-run-source-deploy/kirchhoff:$(date -u +%Y%m%dt%H%M%S)"

(cd "$ROOT/services/api" && uv lock --check) || {
  echo "deploy_api: uv.lock does not match pyproject.toml; ask WS2 to regenerate and commit the lock file (the deploy never rewrites it)." >&2
  exit 1
}
if [ "${FORCE:-0}" != "1" ]; then
  (cd "$ROOT/services/api" && GOOGLE_CLOUD_PROJECT=$P GOOGLE_CLOUD_QUOTA_PROJECT=$P uv run python "$ROOT/infra/live_runs.py") || {
    echo "deploy_api: a live run holds a lease; deploy after it finishes (FORCE=1 only outside judging)." >&2
    exit 1
  }
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
"$ROOT/infra/build_context.sh" "$WORK/ctx" >/dev/null
gcloud builds submit "$WORK/ctx" --project=$P --region=$R --tag="$IMAGE" --quiet

gcloud run deploy kirchhoff-enterprise --project=$P --region=$R --image="$IMAGE" --quiet \
  --service-account="$SA" --no-allow-unauthenticated \
  --min-instances=1 --max-instances=2 --concurrency=40 --cpu=1 --memory=1Gi --cpu-boost --timeout=60 \
  --command=/app/.venv/bin/uvicorn \
  --args=kirchhoff.enterprise.app:create_enterprise_app,--factory,--host,0.0.0.0,--port,8080 \
  --env-vars-file="$ROOT/infra/enterprise.env.yaml"
ENT_URL="$(gcloud run services describe kirchhoff-enterprise --project=$P --region=$R --format='value(status.url)')"
gcloud run services add-iam-policy-binding kirchhoff-enterprise --project=$P --region=$R \
  --member="serviceAccount:$SA" --role=roles/run.invoker --quiet >/dev/null

cp "$ROOT/infra/api.env.yaml" "$WORK/api.env.yaml"
printf 'KIRCHHOFF_ENTERPRISE_URL: "%s"\n' "$ENT_URL" >> "$WORK/api.env.yaml"
gcloud run deploy kirchhoff-api --project=$P --region=$R --image="$IMAGE" --quiet \
  --service-account="$SA" --allow-unauthenticated --no-cpu-throttling \
  --min-instances=1 --max-instances=3 --concurrency=20 --cpu=2 --memory=2Gi --timeout=900 \
  --env-vars-file="$WORK/api.env.yaml"
echo "deployed $IMAGE (kirchhoff-enterprise: $ENT_URL)"
