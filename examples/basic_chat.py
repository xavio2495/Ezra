"""basic_chat — one agent, one turn through the full 8-step router.

The simplest end-to-end use of the SDK: create a session graph, spawn an agent,
and run a turn. The router assembles context (beliefs + memory), calls the model,
writes the turn back to the hot tier, and (because a ``user_id`` is given) runs
the learning meta-agent afterwards.
"""

from __future__ import annotations

import asyncio

from ezra_core.runtime import Ezra

from examples._harness import build_offline_ezra


async def run(ezra: Ezra) -> dict:
    graph = await ezra.create_session_graph(
        session_graph_id="basic-chat", description="single-agent chat"
    )
    agent = await ezra.spawn_agent(
        graph, agent_id="assistant", permission_scope=["strategy"], user_id="demo-user"
    )
    result = await agent.complete(
        "What's a sensible final-stint tyre call at Monaco?",
        system_prompt="You are a concise Formula 1 race strategist.",
    )
    return {
        "response": result.response,
        "context_slots": len(result.context.slots),
        "learning_ran": result.learning_report is not None,
    }


async def _demo() -> None:
    ezra = build_offline_ezra()
    try:
        result = await run(ezra)
        print("response       :", result["response"])
        print("context slots  :", result["context_slots"])
        print("learning ran   :", result["learning_ran"])
    finally:
        await ezra.aclose()


if __name__ == "__main__":
    asyncio.run(_demo())
