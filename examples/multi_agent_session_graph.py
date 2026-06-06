"""multi_agent_session_graph — many agents share one graph + scoped beliefs.

Two agents on one session graph commit beliefs on different topics. The shared
belief store makes each commitment visible to other agents — but only within
their permission scope: the engineer (scope ``[tyres]``) sees the tyre belief but
not the strategy one; the strategist (scope ``[tyres, strategy]``) sees both.
"""

from __future__ import annotations

import asyncio

from ezra_core.runtime import Ezra

from examples._harness import build_offline_ezra


async def run(ezra: Ezra) -> dict:
    graph = await ezra.create_session_graph(
        session_graph_id="multi-agent", description="shared operations graph"
    )
    strategist = await ezra.spawn_agent(
        graph, agent_id="strategist", permission_scope=["tyres", "strategy"]
    )
    engineer = await ezra.spawn_agent(
        graph, agent_id="tyre_engineer", permission_scope=["tyres"]
    )

    await strategist.commit("Plan a one-stop, soft then hard", "strategy", turn_index=1)
    await engineer.commit("Front-left graining from lap 30", "tyres", turn_index=2)

    strat_view = await strategist.belief_snapshot()
    eng_view = await engineer.belief_snapshot()
    return {
        "agents": [a.agent_id for a in graph.active_agents],
        "strategist_sees": sorted(c.topic for c in strat_view.commitments),
        "engineer_sees": sorted(c.topic for c in eng_view.commitments),
    }


async def _demo() -> None:
    ezra = build_offline_ezra()
    try:
        result = await run(ezra)
        print("agents          :", result["agents"])
        print("strategist sees :", result["strategist_sees"])
        print("engineer sees   :", result["engineer_sees"], "(scope-filtered)")
    finally:
        await ezra.aclose()


if __name__ == "__main__":
    asyncio.run(_demo())
