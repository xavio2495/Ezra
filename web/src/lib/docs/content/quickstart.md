# Quickstart

Spin up the Ezra runtime, spawn a scope-bound agent, and run a turn.

## Prerequisites

- **Python 3.12**, packaged with [`uv`](https://docs.astral.sh/uv/).
- Backends: **MongoDB Atlas** (cold tier), **Qdrant** (warm tier), **Redis** (hot tier). For local dev, Redis and Qdrant run as containers via `docker compose up -d redis qdrant`; Atlas is a managed cluster.
- A **Gemini** key (`EZRA_LLM_API_KEY`) for local runs, or **Vertex AI** via Workload Identity on GKE (keyless).

## Install

Ezra is developed in a container (`docker compose run --rm app …`); the package is imported directly from the working tree. To use it from your own project, vendor `ezra_core/` or install it as a path dependency, then sync:

```bash
uv sync --frozen
```

## Configure

Every setting is an `EZRA_*` environment variable read by `EzraSettings` (pydantic-settings). The essentials:

```bash
EZRA_MONGODB_URI="mongodb+srv://…/?retryWrites=true&w=majority"
EZRA_REDIS_URL="redis://localhost:6379"
EZRA_QDRANT_URL="http://localhost:6333"
EZRA_LLM_MODEL="gemini/gemini-3.5-flash"
EZRA_LLM_API_KEY="…"               # AI Studio key (local); omit on GKE (Vertex/WIF)
EZRA_EMBEDDING_MODEL="gemini/gemini-embedding-001"
```

Copy `.env.example` and fill it in; only a subset is read today (see `config.py`).

## Your first agent

```python
import asyncio
from ezra_core.runtime import Ezra


async def main():
    # Build the shared runtime once (Atlas + Redis + Qdrant + checker + LLM).
    ezra = Ezra.from_env()

    # A session graph binds one operation to N concurrent agents.
    graph = await ezra.create_session_graph(
        session_graph_id="race-weekend-monaco-2026",
        merge_strategy="highest_trust",
    )

    # Spawn a scope-bound agent; you get an EzraService back.
    strategist = await ezra.spawn_agent(
        graph,
        agent_id="race_strategy",
        permission_scope=["tyres", "strategy"],
        role="Race strategy engineer.",
        user_id="team-ezra",
    )

    # Run a turn — the router assembles context, calls the model, writes back.
    result = await strategist.complete("What tyre for the final stint?")
    print(result.response)

    await ezra.aclose()


asyncio.run(main())
```

`Ezra.from_env()` is the production composition root. For unit tests, construct `Ezra(...)` directly with in-memory components (fakeredis, an in-memory Qdrant, a fake LLM) — see `tests/unit/test_runtime.py`.

## Commit a belief

`complete()` runs the model. To record a factual commitment (with contradiction detection + reconciliation against the shared belief store):

```python
result = await strategist.commit("Start on mediums, one-stop.", "tyres", turn_index=1)
snapshot = await strategist.belief_snapshot()
print([c.claim for c in snapshot.commitments])
```

## Next

- [Python SDK](/docs/sdk) — the full `Ezra` / `EzraService` surface.
- [Beliefs & Reconciliation](/docs/beliefs) — how contradictions are caught and resolved.
- [Federated Query](/docs/federation) — give an agent live data access.
