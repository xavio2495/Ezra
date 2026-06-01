"""ASGI composition root for the REST API (production entrypoint).

``create_app`` takes injected components so it stays unit-testable; this module
is the thin "wire it from settings" layer the container runs:

    uvicorn ezra_core.api.asgi:app --host 0.0.0.0 --port 8080

With ``EZRA_MONGODB_URI`` set it builds the real cold-tier-backed surface
(Mongo belief store + branch manager). Without it, it still boots a health-only
app so the container is live for readiness probes before Atlas wiring. The
contradiction checker (needs the opt-in ``ml`` deps) and mesh connectors are
left unconfigured here — they are wired per-deployment as needed.
"""

from __future__ import annotations

from ezra_core.api.app import create_app
from ezra_core.config import EzraSettings


def build_app():
    settings = EzraSettings()
    token = settings.api_bearer_token or None

    if not settings.mongodb_uri:
        from ezra_core.belief.store import InMemoryBeliefStore

        return create_app(belief_store=InMemoryBeliefStore(), bearer_token=token)

    from pymongo import AsyncMongoClient

    from ezra_core.belief.branching import BranchManager, MongoBranchStore
    from ezra_core.belief.store import MongoBeliefStore
    from ezra_core.session_graph import MongoSessionGraphStore

    client = AsyncMongoClient(settings.mongodb_uri)
    belief = MongoBeliefStore(client, settings.mongodb_db)
    branches = BranchManager(
        graph_store=MongoSessionGraphStore(client, settings.mongodb_db),
        belief_store=belief,
        branch_store=MongoBranchStore(client, settings.mongodb_db),
    )
    return create_app(belief_store=belief, branch_manager=branches, bearer_token=token)


app = build_app()
