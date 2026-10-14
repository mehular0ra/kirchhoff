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
	cd services/api && uv run python ../../scenarios/demo_world/build.py
