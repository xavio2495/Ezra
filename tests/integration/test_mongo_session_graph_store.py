"""MongoDB-backed store roundtrip. Skipped unless EZRA_MONGODB_URI is set
(set it to the Atlas dev cluster to exercise real persistence)."""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("EZRA_MONGODB_URI"),
    reason="EZRA_MONGODB_URI not set — skipping MongoDB integration test",
)


async def test_mongo_roundtrip():
    from pymongo import AsyncMongoClient

    from ezra_core.session_graph import MongoSessionGraphStore, SessionGraph

    client = AsyncMongoClient(os.environ["EZRA_MONGODB_URI"])
    store = MongoSessionGraphStore(client, os.getenv("EZRA_MONGODB_DB", "ezra_test"))
    graph_id = "it-session-graph"
    try:
        graph = await SessionGraph.create(
            store=store, session_graph_id=graph_id, description="integration"
        )
        await graph.spawn_agent(agent_id="a", permission_scope=["telemetry"])

        reloaded = await SessionGraph.load(graph_id, store)
        assert {r.agent_id for r in reloaded.active_agents} == {"a"}
        assert reloaded.active_agents[0].permission_scope == ["telemetry"]
    finally:
        await store.delete(graph_id)
        await client.close()
