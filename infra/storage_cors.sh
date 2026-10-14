#!/usr/bin/env bash
# Bucket CORS for signed-URL downloads from the web app (P3 R19, obligations §6). Idempotent.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
P=ordinal-mep
BUCKET=gs://ordinal-mep.firebasestorage.app
gcloud storage buckets update $BUCKET --project=$P --cors-file="$ROOT/infra/storage-cors.json"
gcloud storage buckets describe $BUCKET --project=$P --format='json(cors_config)'
