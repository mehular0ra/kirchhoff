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
