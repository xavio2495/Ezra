"""custom_reconciler — application-defined contradiction resolution.

A session graph can use ``merge_strategy="custom"`` with an async resolver that
receives the detected ``Contradiction`` and a ``ResolveContext`` and returns a
``Resolution``. Here the policy is: while only one prior agent holds a claim on
the topic, defer to ``highest_trust``; once two or more agents already conflict on
the topic, escalate to a human (the race director).
"""

from __future__ import annotations

import asyncio

from ezra_core.belief.reconciler import ResolveContext
from ezra_core.runtime import Ezra
from ezra_core.schemas.belief import Contradiction, Resolution

from examples._harness import build_offline_ezra


async def race_director_policy(
    contradiction: Contradiction, ctx: ResolveContext
) -> Resolution:
    if ctx.contemporaneous_contradictions_on_topic(contradiction.topic) >= 2:
        return Resolution.escalate(reason="3+ agents conflict on the same call")
    return Resolution.fallback_to("highest_trust")


async def run(ezra: Ezra) -> dict:
    graph = await ezra.create_session_graph(
        session_graph_id="custom-reconcile",
        merge_strategy="custom",
        custom_resolver=race_director_policy,
    )
    tyre = await ezra.spawn_agent(graph, agent_id="tyre", permission_scope=["tyres"])
    weather = await ezra.spawn_agent(graph, agent_id="weather", permission_scope=["tyres"])
    aero = await ezra.spawn_agent(graph, agent_id="aero", permission_scope=["tyres"])

    # First two conflict -> resolved by the highest_trust fallback (kept, not escalated).
    await tyre.commit("Run softs for outright pace", "tyres", turn_index=1)
    second = await weather.commit("Run wets, rain in 8 minutes", "tyres", turn_index=2)
    # Third agent makes it a 3-way conflict -> the custom policy escalates.
    third = await aero.commit("Run mediums, softs will overheat", "tyres", turn_index=3)

    return {
        "second_decision": second.resolution.decision if second.resolution else None,
        "third_decision": third.resolution.decision if third.resolution else None,
        "third_strategy": third.resolution.merge_strategy_used if third.resolution else None,
    }


async def _demo() -> None:
    ezra = build_offline_ezra()
    try:
        result = await run(ezra)
        print("2nd commit resolved by :", result["second_decision"], "(highest_trust fallback)")
        print("3rd commit resolved by :", result["third_decision"], f"({result['third_strategy']})")
    finally:
        await ezra.aclose()


if __name__ == "__main__":
    asyncio.run(_demo())
