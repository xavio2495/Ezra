"""cross_graph_inheritance — a new graph inherits core memory from prior ones.

Core semantic facts established in one operations period carry forward to the
next: a session graph created with ``inherits_from=[...]`` loads the inherited
graphs' scope-matched core facts at each agent spawn, so a fresh agent starts with
the institutional memory rather than a blank slate. Belief history is NOT
inherited (a new graph's commitments start clean).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from ezra_core.router import hydrate_at_agent_spawn
from ezra_core.runtime import Ezra
from ezra_core.schemas.memory import SemanticFact

from examples._harness import build_offline_ezra

PRIOR_GRAPH = "race-monaco-2025"
NEW_GRAPH = "race-monaco-2026"


async def run(ezra: Ezra) -> dict:
    now = datetime.now(timezone.utc)
    # Institutional knowledge established during the 2025 weekend.
    await ezra.semantic_store.add(
        SemanticFact(
            id=str(uuid4()),
            user_id="team",
            subject="Monaco",
            predicate="overtaking",
            object="near-impossible; track position is decisive",
            tier="core",
            topics=["strategy"],
            confidence=0.95,
            source_session_graph_ids=[PRIOR_GRAPH],
            created_at=now,
            updated_at=now,
        )
    )
    await ezra.create_session_graph(session_graph_id=PRIOR_GRAPH)

    # The 2026 graph inherits from 2025.
    new_graph = await ezra.create_session_graph(
        session_graph_id=NEW_GRAPH, inherits_from=[PRIOR_GRAPH]
    )
    await ezra.spawn_agent(new_graph, agent_id="strategist", permission_scope=["strategy"])
    registration = new_graph.active_agents[-1]

    hydration = await hydrate_at_agent_spawn(
        graph=new_graph.record,
        agent=registration,
        user_id="team",
        semantic_store=ezra.semantic_store,
    )
    return {
        "inherited_facts": [f.object for f in hydration.inherited_core],
        "own_facts": [f.object for f in hydration.own_core],
    }


async def _demo() -> None:
    ezra = build_offline_ezra()
    try:
        result = await run(ezra)
        print("inherited from 2025 :", result["inherited_facts"])
        print("own (2026) core     :", result["own_facts"], "(empty — fresh graph)")
    finally:
        await ezra.aclose()


if __name__ == "__main__":
    asyncio.run(_demo())
