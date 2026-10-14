# Built from the staged context produced by infra/build_context.sh (code + repo scenarios/ + static seed bundles).
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY kirchhoff ./kirchhoff
RUN uv sync --frozen --no-dev
COPY scenarios /app/scenarios
COPY seed /app/seed
ENV PORT=8080 KIRCHHOFF_SCENARIOS_DIR=/app/scenarios KIRCHHOFF_SEED_DIR=/app/seed
CMD ["/app/.venv/bin/uvicorn", "kirchhoff.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
