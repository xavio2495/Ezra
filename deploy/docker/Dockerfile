# Production image for the Ezra Core REST API. Build from the repo root:
#   docker build -f deploy/docker/Dockerfile -t <region>-docker.pkg.dev/<proj>/ezra/ezra-api:<tag> .
#
# Mirrors the dev image (same uv + Python 3.12) but installs runtime deps only
# (`--no-dev`, no opt-in `ml` group) and ships just the ezra_core package.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Dependency layer — lockfiles only, so it caches across source edits.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Only the platform package is needed to serve the API.
COPY ezra_core ./ezra_core

EXPOSE 8080
CMD ["uvicorn", "ezra_core.api.asgi:app", "--host", "0.0.0.0", "--port", "8080"]
