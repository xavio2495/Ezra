"""with_snowflake_source — federated Snowflake query with native time-travel.

An agent queries a Snowflake table through Ezra's pushdown connector. Unlike
MongoDB, Snowflake supports query-time time-travel, so the connector reports
``time_travel_available=True`` and an ``as_of`` argument is compiled to an
``AT (TIMESTAMP => ...)`` clause. The connector runs through an injected executor
(a real Snowflake cursor in production; an in-memory stand-in here).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from ezra_core.mesh.snowflake import SnowflakeConnector
from ezra_core.runtime import Ezra

from examples._harness import build_offline_ezra

_ROWS = [
    {"season": 2023, "circuit": "Monaco", "winner": "VER"},
    {"season": 2024, "circuit": "Monaco", "winner": "LEC"},
]


async def run(ezra: Ezra, *, executor=None) -> dict:
    executor = executor or (lambda sql: _ROWS)  # any SQL -> canned rows
    mesh = SnowflakeConnector(
        "EZRA.PUBLIC.RACE_RESULTS", executor=executor, topics=["strategy"]
    )

    graph = await ezra.create_session_graph(session_graph_id="snowflake-source")
    strategist = await ezra.spawn_agent(
        graph, agent_id="strategist", permission_scope=["strategy"], mesh=mesh
    )

    current = await strategist.query("historical Monaco winners", topics=["strategy"])
    as_of = datetime(2024, 1, 1, tzinfo=timezone.utc)
    historical = await strategist.query("as it stood last season", topics=["strategy"], as_of=as_of)

    return {
        "source": current.provenance.source,
        "time_travel_available": current.provenance.time_travel_available,
        "rows": len(current.data),
        "time_travel_sql": mesh.build_sql("...", as_of=as_of),
        "historical_rows": len(historical.data),
    }


async def _demo() -> None:
    ezra = build_offline_ezra()
    try:
        result = await run(ezra)
        print("source          :", result["source"])
        print("time-travel     :", result["time_travel_available"])
        print("time-travel SQL :", result["time_travel_sql"])
        print("rows            :", result["rows"])
    finally:
        await ezra.aclose()


if __name__ == "__main__":
    asyncio.run(_demo())
