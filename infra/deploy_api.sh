#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../services/api"
uv lock
gcloud run deploy kirchhoff-api --project=ordinal-mep --region=asia-south1 --source=. \
  --allow-unauthenticated --no-cpu-throttling --min-instances=1 --max-instances=3 --concurrency=20 \
  --cpu=2 --memory=2Gi --timeout=900 \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=ordinal-mep,GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_LOCATION=global
