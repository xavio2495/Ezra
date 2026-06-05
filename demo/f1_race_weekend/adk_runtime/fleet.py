"""Full ADK fleet over Ezra against the real federated stores.

This is the Phase-5 superset of the 3-agent slice: it spawns the always-on +
early-event F1 roles as real ``google.adk`` agents, binds the data-capable ones to
*real* mesh connectors (Snowflake historical results, BigQuery historical results),
and runs them against live Atlas + Redis + Qdrant + Gemini. It exercises the core
differentiators on genuine data and output:

  * **Federation** — race_strategy queries Snowflake and aero_rd queries BigQuery
    through Ezra's connectors; every result carries provenance + a time-travel flag.
  * **Permission denial** — logistics is refused an out-of-scope ``aero`` fetch by
    the policy engine (real scope check).
  * **Contradiction** — race_strategy and tyre_engineer both decide a final-stint
    compound on topic ``tyres``; the two-pass checker detects the disagreement and
    the reconciler resolves it by trust.
  * **Branching** — after the turns, a real counterfactual branch is taken from the
    live graph and run forward.

Run as a GKE Job: ``python -m demo.f1_race_weekend.adk_runtime.fleet``.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from pydantic import BaseModel, Field

from demo.f1_race_weekend.adk_runtime.orchestrator import AgentTurn, _run_agent
from demo.f1_race_weekend.agents.roles import role_by_id
from ezra_core.policy.engine import PolicyDeniedError
from ezra_core.runtime import Ezra

FLEET_GRAPH = "race-weekend-monaco-2026-fleet"
INHERITED_GRAPH = "race-weekend-imola-2026"

# Always-on + FP1 roles for the live fleet (a credible peak without exhausting the
# Gemini rate limit on a single run).
FLEET_ROLES = (
    "race_strategy", "tyre_engineer", "aero_rd", "logistics",
    "telemetry_analyst", "weather_model",
)

# Role-appropriate briefings: data-capable roles are told to fetch first.
FLEET_PROMPTS = {
    "race_strategy": (
        "Lap 45 at Monaco. First call fetch_federated for historical Monaco results "
        "(topic 'strategy') to ground your call, then decide the final-stint tyre and "
        "commit it as a belief on topic 'tyres' in one short sentence. Track position "
        "is critical — favour the fastest compound. Commit now."
    ),
    "tyre_engineer": (
        "Lap 45 at Monaco. Rear surface temps are 52°C and the softs are graining and "
        "will not last. Decide the final-stint tyre and commit it as a belief on topic "
        "'tyres' in one short sentence — protect tyre life. Commit now."
    ),
    "aero_rd": (
        "Monaco final stint. First call fetch_federated for historical results (topic "
        "'aero') for context, then commit one short downforce recommendation as a "
        "belief on topic 'aero'. Commit now."
    ),
    "logistics": (
        "Confirm the parts and logistics posture for the final stint. Commit one short "
        "belief on topic 'parts'. Commit now."
    ),
    "telemetry_analyst": (
        "Summarise the car's current telemetry posture and commit one short belief on "
        "topic 'telemetry'. Commit now."
    ),
    "weather_model": (
        "Radar shows a 30% chance of light rain in ~15 minutes. Commit your forecast as "
        "a belief on topic 'weather' in one short sentence. Commit now."
    ),
}


class FleetResult(BaseModel):
    graph_id: str
    turns: list[AgentTurn] = Field(default_factory=list)
    contradictions: list[dict] = Field(default_factory=list)
    federated_fetches: list[dict] = Field(default_factory=list)
    denial: Optional[dict] = None
    branch_diff: Optional[dict] = None
    final_beliefs: list[dict] = Field(default_factory=list)


def _mesh_for(ezra: Ezra, role_id: str):
    """Bind data-capable roles to a real warehouse connector (None for others)."""
    from ezra_core.mesh.connectors import (
        bigquery_connector_from_settings,
        snowflake_connector_from_settings,
    )

    s = ezra.settings
    if role_id == "race_strategy" and s.snowflake_account:
        return snowflake_connector_from_settings(
            s, f"{s.snowflake_database}.{s.snowflake_schema}.RACE_RESULTS", topics=["strategy"]
        )
    if role_id == "aero_rd" and s.bigquery_project:
        table = f"{s.bigquery_project}.{s.bigquery_dataset}.race_results"
        return bigquery_connector_from_settings(s, table, topics=["aero"])
    return None


async def run_fleet(ezra: Ezra, *, trust: Optional[dict] = None) -> FleetResult:
    trust = trust or {"tyre_engineer": 0.95, "race_strategy": 0.80}

    graph = await ezra.create_session_graph(
        session_graph_id=FLEET_GRAPH,
        description="Monaco GP live ADK fleet",
        merge_strategy="highest_trust",
        inherits_from=[INHERITED_GRAPH],
    )

    services = {}
    for role_id in FLEET_ROLES:
        role = role_by_id(role_id)
        services[role_id] = await ezra.spawn_agent(
            graph,
            agent_id=role.agent_id,
            permission_scope=role.permission_scope,
            role=role.role,
            mesh=_mesh_for(ezra, role_id),
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
            services[role_id], role_by_id(role_id), FLEET_PROMPTS[role_id],
            ezra.settings.llm_model, ezra.settings.llm_api_key, events,
        )

    # Stagger only the two 'tyres' contestants so their commits serialize.
    delays = {"tyre_engineer": 8.0}
    turns = await asyncio.gather(
        *(_staggered(r, delays.get(r, 0.0)) for r in FLEET_ROLES)
    )

    # Permission-denial beat: logistics is refused an out-of-scope 'aero' fetch.
    denial = None
    try:
        await services["logistics"].query("aero downforce target?", topics=["aero"])
    except PolicyDeniedError as exc:
        denial = {"agent": "logistics", "denied_topic": exc.topic,
                  "scope": services["logistics"].permission_scope}

    # Branching beat: a real counterfactual from the live graph.
    branch_diff = None
    if ezra.branch_manager is not None:
        try:
            await ezra.branch_manager.branch_from(
                session_graph_id=FLEET_GRAPH, turn=1, branch_id=f"{FLEET_GRAPH}-whatif"
            )
            await ezra.branch_manager.mutate_belief(
                branch_id=f"{FLEET_GRAPH}-whatif", agent_id="race_strategy",
                new_claim="wets called at lap 43", topic="tyres", turn_index=2,
            )
            diff = await ezra.branch_manager.diff_branches(
                original=FLEET_GRAPH, branch=f"{FLEET_GRAPH}-whatif", from_turn=1
            )
            branch_diff = {"diverged": diff.diverged_commitments}
        except Exception as exc:  # branching is best-effort in the live run
            branch_diff = {"error": str(exc)[:200]}

    snap = await ezra.belief_store.get_active(FLEET_GRAPH)
    return FleetResult(
        graph_id=FLEET_GRAPH,
        turns=list(turns),
        contradictions=[e for e in events if e.get("kind") == "contradiction"],
        federated_fetches=[e for e in events if e.get("kind") == "fetch"],
        denial=denial,
        branch_diff=branch_diff,
        final_beliefs=[
            {"agent": c.agent_id, "topic": c.topic, "claim": c.claim} for c in snap
        ],
    )


async def _main() -> None:  # pragma: no cover - GKE Job entrypoint
    from ezra_core.config import EzraSettings
    from ezra_core.runtime import gemini_checker
    from ezra_core.secret_files import load_secret_files

    load_secret_files()  # GKE: Secret Manager CSI files → EZRA_* env
    settings = EzraSettings()
    ezra = Ezra.from_settings(settings, build_checker=False)
    ezra.checker = gemini_checker(settings)  # two-pass, no torch
    try:
        result = await run_fleet(ezra)
        print("=== FLEET TURNS ===")
        for t in result.turns:
            print(f"[{t.agent_id}] committed={t.committed}")
        print("\n=== FEDERATED FETCHES ===", result.federated_fetches)
        print("=== CONTRADICTIONS ===", result.contradictions)
        print("=== PERMISSION DENIAL ===", result.denial)
        print("=== BRANCH DIFF ===", result.branch_diff)
        print("\n=== ACTIVE TEAM BELIEFS ===")
        for b in result.final_beliefs:
            print("  ", b)
    finally:
        await ezra.aclose()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(_main())
