"""with_mongodb_source — bind an agent to a federated MongoDB source.

An agent queries a MongoDB collection through Ezra's mesh connector. Every result
carries provenance; MongoDB has no query-time time-travel, so the connector
reports ``time_travel_available=False`` (see with_snowflake_source for the
time-travel case). In production the collection is an Atlas collection reached via
the official MongoDB MCP server; here it's an in-memory stand-in.
"""

from __future__ import annotations

import asyncio

from ezra_core.mesh.mongodb_mcp import MongoMcpConnector
from ezra_core.runtime import Ezra

from examples._harness import build_offline_ezra, demo_mongo_collection


async def run(ezra: Ezra, *, collection=None) -> dict:
    collection = collection or demo_mongo_collection(
        [
            {"lap": 31, "compound": "soft", "deg_pct": 42},
            {"lap": 32, "compound": "soft", "deg_pct": 47},
        ]
    )
    mesh = MongoMcpConnector(collection, source_name="telemetry", topics=["telemetry"])

    graph = await ezra.create_session_graph(session_graph_id="mongo-source")
    analyst = await ezra.spawn_agent(
        graph, agent_id="telemetry_analyst", permission_scope=["telemetry"], mesh=mesh
    )

    result = await analyst.query("{}", topics=["telemetry"])  # find-all filter
    return {
        "source": result.provenance.source,
        "time_travel_available": result.provenance.time_travel_available,
        "rows": len(result.data),
    }


async def _demo() -> None:
    ezra = build_offline_ezra()
    try:
        result = await run(ezra)
        print("source              :", result["source"])
        print("time-travel         :", result["time_travel_available"], "(MongoDB: none)")
        print("rows                :", result["rows"])
    finally:
        await ezra.aclose()


if __name__ == "__main__":
    asyncio.run(_demo())
