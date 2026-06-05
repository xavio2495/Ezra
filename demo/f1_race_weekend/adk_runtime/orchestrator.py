"""Drive the real ADK multi-agent fleet over Ezra.

``run_slice`` is the Phase-2 vertical slice: three agents (race_strategy,
tyre_engineer, weather_model) each get a real ADK ``Agent`` wired to a scope-bound
``EzraService`` on one shared session graph. They run concurrently on a final-stint
prompt; because they share Ezra's belief store, their independent Gemini outputs
land as commitments on the same topic and a genuine contradiction is detected and
reconciled by the platform — nothing is staged.

The graph uses ``highest_trust`` so the contradiction resolves deterministically
once the agents' per-topic trust differs. Trust is seeded on the registrations so
the slice has a defined winner to assert on.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from pydantic import BaseModel, Field

from demo.f1_race_weekend.adk_runtime.agents import build_adk_agent
from demo.f1_race_weekend.agents.roles import role_by_id
from ezra_core.runtime import Ezra

SLICE_GRAPH = "race-weekend-monaco-2026-live"
SLICE_ROLES = ("race_strategy", "tyre_engineer", "weather_model")

# Per-role briefings. A genuine contradiction needs two agents whose remit both
# covers the contested topic ('tyres') given OPPOSING evidence — real permission
# scoping blocks the original cross-topic "contradiction". race_strategy and
# tyre_engineer both hold 'tyres' and are pushed to different compounds; the
# weather agent commits on its own remit ('weather') and adds fleet texture
# without a forced cross-scope conflict.
SLICE_PROMPTS = {
    "race_strategy": (
        "Lap 45 at Monaco, dry line. Track position is everything here and the car "
        "behind is closing on fresher rubber. You must defend with the fastest "
        "compound. Decide the final-stint tyre and commit it as a belief on topic "
        "'tyres' in one short sentence. Commit now — do not wait for more data."
    ),
    "tyre_engineer": (
        "Lap 45 at Monaco. Rear surface temps are 52°C and the softs are graining "
        "badly — they will not survive the stint. You must protect tyre life. Decide "
        "the final-stint tyre and commit it as a belief on topic 'tyres' in one short "
        "sentence. Commit now — do not wait for more data."
    ),
    "weather_model": (
        "Lap 45 at Monaco. Radar shows a 30% chance of light rain in ~15 minutes. "
        "Commit your forecast as a belief on topic 'weather' in one short sentence. "
        "Commit now — do not wait for more data."
    ),
}


class AgentTurn(BaseModel):
    agent_id: str
    response: str
    committed: list[dict] = Field(default_factory=list)


class SliceResult(BaseModel):
    graph_id: str
    turns: list[AgentTurn] = Field(default_factory=list)
    contradictions: list[dict] = Field(default_factory=list)
    final_beliefs: list[dict] = Field(default_factory=list)


async def _run_agent(
    service, role, prompt: str, llm_model: str, api_key: str = "", events: list | None = None
) -> AgentTurn:
    """Run a single turn of an already-spawned agent; return response + commitments."""
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    agent, _ = build_adk_agent(
        role, service, llm_model=llm_model, api_key=api_key, events=events
    )

    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="ezra-f1", user_id="team-ezra", session_id=role.agent_id
    )
    runner = Runner(app_name="ezra-f1", agent=agent, session_service=session_service)

    response_text = ""
    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    async for event in runner.run_async(
        user_id="team-ezra", session_id=role.agent_id, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            response_text = "".join(p.text or "" for p in event.content.parts)

    snap = await service.belief_snapshot()
    committed = [
        {"topic": c.topic, "claim": c.claim}
        for c in snap.commitments
        if c.agent_id == role.agent_id
    ]
    return AgentTurn(agent_id=role.agent_id, response=response_text, committed=committed)


async def run_slice(
    ezra: Ezra,
    *,
    prompts: Optional[dict[str, str]] = None,
    trust: Optional[dict[str, float]] = None,
    stagger_seconds: float = 6.0,
) -> SliceResult:
    """Run the 3-agent final-stint slice on a fresh graph; return what happened.

    The two 'tyres' contestants (race_strategy, tyre_engineer) are launched with a
    small stagger so their commits serialize — detection is point-in-time, so two
    simultaneous commits could each miss the other. The fleet still runs
    concurrently (the weather agent overlaps); the stagger only orders the pair
    that is meant to collide.
    """
    prompts = prompts or SLICE_PROMPTS
    # Seed per-topic trust so highest_trust has a defined winner (tyre_engineer
    # over race_strategy on 'tyres').
    trust = trust or {"tyre_engineer": 0.95, "race_strategy": 0.80, "weather_model": 0.90}

    graph = await ezra.create_session_graph(
        session_graph_id=SLICE_GRAPH,
        description="Live ADK final-stint slice",
        merge_strategy="highest_trust",
    )

    # Spawn all agents first, then seed per-topic trust on their registrations
    # BEFORE any turn runs — so highest_trust reconciliation (which reads trust
    # live via the runtime's trust_for closure) has a defined winner.
    services = {}
    for role_id in SLICE_ROLES:
        role = role_by_id(role_id)
        services[role_id] = await ezra.spawn_agent(
            graph,
            agent_id=role.agent_id,
            permission_scope=role.permission_scope,
            role=role.role,
        )
    for reg in graph.active_agents:
        if reg.agent_id in trust:
            reg.trust_scores["tyres"] = trust[reg.agent_id]
    await ezra.graph_store.save(graph.record)

    events: list[dict] = []

    async def _staggered(role_id: str, delay: float) -> AgentTurn:
        if delay:
            await asyncio.sleep(delay)
        return await _run_agent(
            services[role_id],
            role_by_id(role_id),
            prompts[role_id],
            ezra.settings.llm_model,
            ezra.settings.llm_api_key,
            events,
        )

    # race_strategy commits first; tyre_engineer follows after the stagger and
    # detects the contradiction; weather runs in parallel on its own topic.
    delays = {"race_strategy": 0.0, "tyre_engineer": stagger_seconds, "weather_model": 0.0}
    turns = await asyncio.gather(
        *(_staggered(role_id, delays.get(role_id, 0.0)) for role_id in SLICE_ROLES)
    )

    snap = await ezra.belief_store.get_active(SLICE_GRAPH)
    result = SliceResult(
        graph_id=SLICE_GRAPH,
        turns=list(turns),
        contradictions=events,
        final_beliefs=[
            {"agent": c.agent_id, "topic": c.topic, "claim": c.claim} for c in snap
        ],
    )
    return result


async def _main() -> None:  # pragma: no cover - script entry point
    from rich.console import Console
    from rich.panel import Panel

    ezra = Ezra.from_env(build_checker=False)
    # Lean two-pass checker (Gemini, no torch) so contradictions are real locally.
    from ezra_core.runtime import gemini_checker

    ezra.checker = gemini_checker(ezra.settings)
    console = Console()
    try:
        result = await run_slice(ezra)
        for turn in result.turns:
            console.print(
                Panel(
                    f"[bold]{turn.agent_id}[/bold]\n{turn.response}\n\n"
                    f"committed: {turn.committed}",
                    title=turn.agent_id,
                )
            )
        console.print(Panel(str(result.final_beliefs), title="Active team beliefs"))
    finally:
        await ezra.aclose()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(_main())
