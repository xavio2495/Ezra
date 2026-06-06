"""intent_fetch — the router infers a fetch from intent and translates NL→native.

Demonstrates router step 1 (Parse) → step 5 (intent-driven Fetch) → connector-level
NL→native query translation, end to end and offline:

  * a HeuristicIntentParser flags the data-seeking input as needing a fetch,
  * a Snowflake connector (column allowlist + a fake translator standing in for
    the LLM) turns the intent into a constrained, validated pushdown query,
  * a fake executor runs it and returns rows.

In production the parser + translator are Gemini-backed (see parser_from_settings
/ translator_from_settings); the same router/connector code runs.
"""

from __future__ import annotations

import asyncio

from ezra_core.mesh.snowflake import SnowflakeConnector
from ezra_core.mesh.translate import SqlPredicate
from ezra_core.parse import HeuristicIntentParser
from ezra_core.runtime import Ezra

from examples._harness import build_offline_ezra

_ROWS = [
    {"season": 2023, "circuit": "Monaco", "winner": "VER"},
    {"season": 2024, "circuit": "Monaco", "winner": "LEC"},
]
COLUMNS = {"season": "int", "circuit": "str", "winner": "str"}


class _DemoTranslator:
    """Offline stand-in for the LLM translator: turns the Monaco question into a
    constrained predicate (the real one asks Gemini)."""

    def to_sql(self, intent, *, columns):
        return SqlPredicate(projection=["season", "winner"], where="circuit = 'Monaco'", limit=50)

    def to_mongo_filter(self, intent, *, columns):
        return {}


async def run(ezra: Ezra) -> dict:
    captured = {}

    def executor(sql: str):
        captured["sql"] = sql
        return _ROWS

    mesh = SnowflakeConnector(
        "EZRA.PUBLIC.RACE_RESULTS",
        executor=executor,
        topics=["strategy"],
        columns=COLUMNS,
        translator=_DemoTranslator(),
    )

    graph = await ezra.create_session_graph(session_graph_id="intent-fetch")
    # spawn_agent wires the agent's Router; attach the parser + mesh for this agent.
    ezra.parser = HeuristicIntentParser()
    svc = await ezra.spawn_agent(
        graph, agent_id="strategist", permission_scope=["strategy"], mesh=mesh
    )

    # No explicit mesh_query — the router parses the intent and decides to fetch.
    result = await svc.complete("what were the historical Monaco results?")
    return {
        "needs_fetch": result.parsed_intent.needs_fetch if result.parsed_intent else None,
        "translated_sql": captured.get("sql"),
        "rows": len(result.mesh_result.data) if result.mesh_result else 0,
    }


async def _demo() -> None:
    ezra = build_offline_ezra()
    try:
        result = await run(ezra)
        print("parser flagged fetch :", result["needs_fetch"])
        print("translated SQL       :", result["translated_sql"])
        print("rows returned        :", result["rows"])
    finally:
        await ezra.aclose()


if __name__ == "__main__":
    asyncio.run(_demo())
