#!/usr/bin/env bash
# Dedicated least-privilege runtime identity for kirchhoff-api and kirchhoff-enterprise (P0 R8, review M-12).
# Idempotent. roles/run.invoker on kirchhoff-enterprise is granted by deploy_api.sh once the service exists.
set -euo pipefail
P=ordinal-mep
SA_NAME=kirchhoff-runtime
SA="${SA_NAME}@${P}.iam.gserviceaccount.com"
BUCKET=gs://ordinal-mep.firebasestorage.app

gcloud services enable iamcredentials.googleapis.com --project=$P
if ! gcloud iam service-accounts describe "$SA" --project=$P >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" --project=$P --display-name="Kirchhoff Cloud Run runtime"
fi
for role in roles/datastore.user roles/aiplatform.user roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding $P --member="serviceAccount:$SA" --role="$role" --condition=None \
    --quiet >/dev/null
done
gcloud storage buckets add-iam-policy-binding $BUCKET --project=$P --member="serviceAccount:$SA" \
  --role=roles/storage.objectAdmin >/dev/null
gcloud iam service-accounts add-iam-policy-binding "$SA" --project=$P --member="serviceAccount:$SA" \
  --role=roles/iam.serviceAccountTokenCreator >/dev/null
echo "runtime service account ready: $SA"
