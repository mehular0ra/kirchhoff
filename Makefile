.PHONY: test gen-types check-types dev-api dev-web
test:
	cd services/api && uv run pytest -q
	cd apps/web && npm test
gen-types:
	cd services/api && uv run python -m kirchhoff.contracts.export_schema build/schema.json
	cd apps/web && npm run gen-types
check-types: gen-types
	git diff --exit-code apps/web/src/contracts/generated.ts
dev-api:
	cd services/api && GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_LOCATION=global uv run uvicorn kirchhoff.api.app:create_app --factory --port 8080 --reload
dev-web:
	cd apps/web && npm run dev

# ---- WS4: deploy, demo world, e2e (docs/superpowers/plans/2026-10-13-p4-enterprise-demo-infra.md) ----
GCP_ENV = GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep
.PHONY: deploy-api deploy-web deploy smoke seed-enterprise demo-world
deploy-api:
	./infra/deploy_api.sh
deploy-web:
	./infra/deploy_web.sh
deploy: deploy-api deploy-web smoke
smoke:
	./infra/smoke.sh
seed-enterprise:
	cd services/api && $(GCP_ENV) uv run python -m kirchhoff.enterprise.seed_cli --docs ../../apps/web/public/demo/files
demo-world:
	cd services/api && uv run python ../../scenarios/demo_world/build.py && uv run python ../../scenarios/demo_world/build_inbox.py

# End-to-end browser tests (Playwright, e2e/). `make e2e-local` needs no cloud access: it serves apps/web and blocks Google.
E2E_TOKEN = $$(gcloud secrets versions access latest --secret=kirchhoff-e2e-appcheck-debug-token --project=ordinal-mep 2>/dev/null)
.PHONY: e2e-install e2e-local e2e-static e2e-live e2e
e2e-install:
	cd e2e && npm ci && npx playwright install chromium
e2e-local: e2e-install
	cd e2e && E2E_LOCAL=1 npx playwright test --project=static --project=phone
e2e-static: e2e-install
	cd e2e && APPCHECK_DEBUG_TOKEN="$(E2E_TOKEN)" npx playwright test --project=static --project=phone
e2e-live: e2e-install
	cd e2e && E2E_LIVE=1 APPCHECK_DEBUG_TOKEN="$(E2E_TOKEN)" npx playwright test --project=live
e2e: e2e-static
