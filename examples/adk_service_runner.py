"""adk_service_runner — Ezra registered as a real Google ADK service.

Builds a real ``google.adk`` ``Agent`` whose tools are an :class:`EzraToolset`
and a ``Runner`` whose ``memory_service`` is an :class:`EzraMemoryService`, then
exercises the full surface: commit two beliefs, rewind the live graph, git-revert
a single belief, and search memory — all through the registered ADK objects.

The offline run drives the tools + memory service directly (deterministic, no
model). The same Agent/Toolset/MemoryService are what a real ``Runner`` loop +
LLM drive in the live GKE/Vertex smoke — only the model differs.

Requires the optional ``agents`` dependency (``google-adk``).
"""

from __future__ import annotations

import asyncio

from ezra_core.adk_service import EzraMemoryService, EzraToolset, build_ezra_agent
from ezra_core.runtime import Ezra

from examples._harness import build_offline_ezra


async def run(ezra: Ezra) -> dict:
    graph = await ezra.create_session_graph(
        session_graph_id="adk-memory", merge_strategy="last_write_wins"
    )
    service = await ezra.spawn_agent(
        graph, agent_id="strategist", permission_scope=["tyres", "strategy"], user_id="team"
    )

    # Register Ezra with ADK: a Toolset on the agent + a MemoryService on a Runner.
    agent, _ = build_ezra_agent(
        service, name="strategist", model="gemini/gemini-2.5-flash",
        instruction="You strategise.",
    )
    toolset = EzraToolset(service)
    memory = EzraMemoryService(ezra, session_graph_id="adk-memory", scope_topics={"tyres"})

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    runner = Runner(
        app_name="ezra-adk",
        agent=agent,
        session_service=InMemorySessionService(),
        memory_service=memory,
    )

    tools = {t.name: t for t in await toolset.get_tools()}

    # commit two beliefs (distinct topics, both stay active), then rewind past
    # the second, then git-revert the first.
    c1 = await service.commit("start on softs", "tyres", turn_index=1)
    await service.commit("plan a one-stop", "strategy", turn_index=2)
    before = {c.claim for c in (await service.belief_snapshot()).commitments}

    rewind = await tools["rewind_beliefs"].func(turn=1, reason="reset to opening call")
    after_rewind = {c.claim for c in (await service.belief_snapshot()).commitments}

    revert = await tools["revert_belief"].func(
        commitment_id=c1.commitment.id, reason="opening call was wrong"
    )
    after_revert = {c.claim for c in (await service.belief_snapshot()).commitments}

    # exercise the memory service search path.
    found = await memory.search_memory(app_name="ezra-adk", user_id="team", query="softs")

    return {
        "runner_has_memory_service": runner.memory_service is memory,
        "tool_names": sorted(tools),
        "before_rewind": sorted(before),
        "after_rewind": sorted(after_rewind),
        "rewind_undone": rewind["undone"],
        "after_revert": sorted(after_revert),
        "revert_status": revert["status"],
        "memory_hits": len(found.memories),
    }


async def _demo() -> None:
    ezra = build_offline_ezra()
    try:
        result = await run(ezra)
        print("registered ADK memory service :", result["runner_has_memory_service"])
        print("ezra tools on the agent       :", result["tool_names"])
        print("beliefs before rewind         :", result["before_rewind"])
        print("after rewind to turn 1        :", result["after_rewind"],
              f"(undone: {result['rewind_undone']})")
        print("after git-revert of opener    :", result["after_revert"])
        print("memory search hits            :", result["memory_hits"])
    finally:
        await ezra.aclose()


if __name__ == "__main__":
    asyncio.run(_demo())
