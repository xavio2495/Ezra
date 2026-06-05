# Dev/test image for the ezra_core platform. Mirrors prod: same uv + Python 3.12.
# The project env lives at /opt/venv (NOT /app/.venv) so the compose bind-mount
# of the source at /app never shadows the installed dependencies.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependency layer — only the lockfiles, so it caches across source edits.
# (pyproject sets `package = false`, so no project build is needed.)
# `--group agents` adds google-adk (real multi-agent demo); `--group ingest` adds
# the Snowflake + BigQuery + FastF1 SDKs so the federated connectors run in-container.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --group agents --group ingest

# Source is bind-mounted in dev (compose); copied here for standalone runs.
COPY . .

CMD ["uv", "run", "pytest", "-q"]
