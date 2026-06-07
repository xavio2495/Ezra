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
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from demo.f1_race_weekend.adk_runtime.orchestrator import AgentTurn, _run_agent
from demo.f1_race_weekend.agents.roles import role_by_id
from ezra_core.policy.engine import PolicyDeniedError
from ezra_core.runtime import Ezra

# Sentinel markers so a one-off GKE Job's JSON snapshot is greppable from the
# pod logs without parsing the surrounding human-readable output.
SNAPSHOT_BEGIN = "===EZRA_DASHBOARD_SNAPSHOT_BEGIN==="
SNAPSHOT_END = "===EZRA_DASHBOARD_SNAPSHOT_END==="

FLEET_GRAPH = "race-weekend-monaco-2026-fleet"
INHERITED_GRAPH = "race-weekend-imola-2026"

# Always-on + FP1 roles for the live fleet (a credible peak without exhausting the
# Gemini rate limit on a single run).
FLEET_ROLES = (
    "race_strategy", "tyre_engineer", "aero_rd", "logistics",
    "telemetry_analyst", "weather_model",
)

# Role-appropriate briefings: data-capable roles are told to fetch first.
# Briefings. The two 'tyres' contestants are forced into a fixed short format so
# their opposing calls have enough lexical overlap for the two-pass checker's
# embedding first-pass to catch the real cross-agent contradiction (verbose,
# differently-worded claims slip under the cosine gate). Every agent is told to
# commit EXACTLY ONCE so the append-only log isn't polluted with reworded re-commits.
FLEET_PROMPTS = {
    "race_strategy": (
        "Lap 45 at Monaco. Call fetch_federated once for historical Monaco results "
        "(topic 'strategy') to ground your call. Track position is critical and the "
        "softs are the fastest compound. You MUST then call commit_belief on topic "
        "'tyres' with EXACTLY this claim and nothing else: 'Final stint: softs.' Do "
        "not end your turn until you have called commit_belief once. Commit now."
    ),
    "tyre_engineer": (
        "Lap 45 at Monaco. Rear surface temps are 52°C and the softs are graining and "
        "will not last — you must protect tyre life with the hard compound. You MUST "
        "call commit_belief on topic 'tyres' with EXACTLY this claim and nothing else: "
        "'Final stint: hards.' Do not end your turn until you have called commit_belief "
        "once. Commit now."
    ),
    "aero_rd": (
        "Monaco final stint. First call fetch_federated for historical results (topic "
        "'aero') for context, then commit one short downforce recommendation as a "
        "belief on topic 'aero'. Call commit_belief exactly once, then stop."
    ),
    "logistics": (
        "Confirm the parts and logistics posture for the final stint. Commit one short "
        "belief on topic 'parts'. Call commit_belief exactly once, then stop."
    ),
    "telemetry_analyst": (
        "Summarise the car's current telemetry posture and commit one short belief on "
        "topic 'telemetry'. Call commit_belief exactly once, then stop."
    ),
    "weather_model": (
        "Radar shows a 30% chance of light rain in ~15 minutes. Commit your forecast as "
        "a belief on topic 'weather' in one short sentence. Call commit_belief exactly "
        "once, then stop."
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
        # Snowflake = historical race results (time-travel warehouse).
        return snowflake_connector_from_settings(
            s, f"{s.snowflake_database}.{s.snowflake_schema}.RACE_RESULTS", topics=["strategy"]
        )
    if role_id == "aero_rd" and s.bigquery_project:
        # BigQuery = engineering/aero analytics — aero_rd's own domain.
        table = f"{s.bigquery_project}.{s.bigquery_dataset}.aero_configs"
        return bigquery_connector_from_settings(s, table, topics=["aero"])
    if role_id == "telemetry_analyst" and s.atlas_streams_processor:
        # Atlas Stream Processing = live telemetry time-series (partner track).
        from ezra_core.mesh.atlas_streams import atlas_streams_connector_from_settings

        return atlas_streams_connector_from_settings(s, topics=["telemetry"])
    return None


async def run_fleet(ezra: Ezra, *, trust: Optional[dict] = None) -> FleetResult:
    trust = trust or {"tyre_engineer": 0.95, "race_strategy": 0.80}

    # Demo hygiene: the belief log is append-only, and this fleet reuses one
    # graph id — so without isolating the run, the snapshot would mix prior runs'
    # commitments. Best-effort clear this graph's (and its what-if branch's) log
    # so the recorded snapshot reflects exactly one run.
    coll = getattr(ezra.belief_store, "_c", None)
    if coll is not None:
        try:
            await coll.delete_many(
                {"session_graph_id": {"$in": [FLEET_GRAPH, f"{FLEET_GRAPH}-whatif"]}}
            )
        except Exception:
            pass

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

    # Stagger the two 'tyres' contestants so their commits serialize. The
    # lower-trust race_strategy must land FIRST (it does a slow Snowflake fetch),
    # so the higher-trust tyre_engineer's later commit triggers accept_new and
    # supersedes the loser — a coherent single belief on the topic.
    delays = {"tyre_engineer": 15.0}
    turns = await asyncio.gather(
        *(_staggered(r, delays.get(r, 0.0)) for r in FLEET_ROLES)
    )

    # Record each real turn into the hot-tier recent-turns ring — its actual
    # purpose — so the session's working memory reflects what genuinely ran.
    for t in turns:
        try:
            await ezra.hot.append_turn(
                FLEET_GRAPH, t.agent_id,
                {"response": t.response, "committed": t.committed},
            )
        except Exception:  # hot-tier write is best-effort; never fail the run
            pass

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


async def capture_snapshot(ezra: Ezra, result: FleetResult) -> dict:
    """Build the enriched dashboard snapshot from a completed fleet run.

    Everything here is read back from the live runtime after ``run_fleet`` — the
    real agents + their scopes/trust, the full append-only belief log (active and
    superseded), the contradiction/reconciliation trace that genuinely fired, the
    federated fetches with provenance, the permission denial, and the branch diff.
    Serialised to JSON and baked into the web ``/dashboard`` so the page shows a
    real recorded run, not a simulation.
    """
    from ezra_core.schemas.belief import MARKER_TYPES

    record = await ezra.graph_store.get(result.graph_id)
    trust_by_id: dict[str, dict] = {}
    if record is not None:
        for reg in record.active_agents:
            trust_by_id[reg.agent_id] = dict(reg.trust_scores)

    log = [
        c
        for c in await ezra.belief_store.get_all(result.graph_id)
        if c.type not in MARKER_TYPES
    ]
    active_ids = {c.id for c in log if not c.superseded and not c.redacted}
    committed_agents = {c.agent_id for c in log}

    agents = []
    for role_id in FLEET_ROLES:
        role = role_by_id(role_id)
        agents.append(
            {
                "id": role.agent_id,
                "role": role.role,
                "scope": role.permission_scope,
                "committed": role.agent_id in committed_agents,
                "trust_tyres": trust_by_id.get(role.agent_id, {}).get("tyres"),
            }
        )

    hot_turns = 0
    for role_id in FLEET_ROLES:
        try:
            hot_turns += len(
                await ezra.hot.get_turns(result.graph_id, role_by_id(role_id).agent_id)
            )
        except Exception:
            pass

    # Reconciliation trace: prefer a cross-agent contradiction (an agent
    # contradicting its own re-commit isn't the showcase); fall back to the first.
    reconciliation = None
    loser_key = None
    if result.contradictions:
        cross = [
            e for e in result.contradictions if e.get("new_agent") != e.get("with_agent")
        ]
        ev = cross[0] if cross else result.contradictions[0]
        accepted = ev.get("decision") == "accept_new"
        winner = ev.get("new_agent") if accepted else ev.get("with_agent")
        loser = ev.get("with_agent") if accepted else ev.get("new_agent")
        loser_key = (loser, ev.get("topic"))
        reconciliation = {
            "topic": ev.get("topic"),
            "similarity": ev.get("similarity"),
            "nli_confidence": ev.get("nli_confidence"),
            "strategy": ev.get("strategy"),
            "decision": ev.get("decision"),
            "winner": winner,
            "loser": loser,
            "winner_trust": trust_by_id.get(winner, {}).get("tyres"),
            "loser_trust": trust_by_id.get(loser, {}).get("tyres"),
        }

    # Display beliefs: one representative claim per (agent, topic). A chatty agent
    # can re-commit reworded variants in a turn; the dashboard shows each agent's
    # authoritative position — the reconciliation loser shows its superseded claim,
    # everyone else their active one. The full append-only count stays in
    # tiers.cold_commitments.
    groups: dict = {}
    for c in log:
        groups.setdefault((c.agent_id, c.topic), []).append(c)
    beliefs = []
    for key, cs in groups.items():
        superseded = [c for c in cs if c.superseded]
        active = [c for c in cs if not c.superseded]
        if key == loser_key and superseded:
            pick = superseded[0]
        elif active:
            pick = active[0]
        else:
            pick = (superseded or cs)[0]
        beliefs.append(
            {
                "agent": pick.agent_id,
                "topic": pick.topic,
                "claim": pick.claim,
                "turn": pick.turn_index,
                "trust": pick.trust_score,
                "active": pick.id in active_ids,
                "superseded": pick.superseded,
            }
        )
    beliefs.sort(key=lambda b: (b["topic"], b["agent"]))

    return {
        "meta": {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "graph_id": result.graph_id,
            "inherited_from": INHERITED_GRAPH,
            "llm_model": ezra.settings.llm_model,
            "sources": ["MongoDB Atlas", "Snowflake", "BigQuery"],
        },
        "agents": agents,
        "tiers": {
            "hot_turns": hot_turns,
            "warm_summaries": 0,
            "cold_commitments": len(log),
            "active_beliefs": len(active_ids),
            "superseded_beliefs": len(log) - len(active_ids),
        },
        "beliefs": beliefs,
        "reconciliation": reconciliation,
        "federated_fetches": result.federated_fetches,
        "denial": result.denial,
        "branch": result.branch_diff,
    }


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
        # Learning meta-agent: damped per-topic trust after any reconciliation
        # (wired live via spawn_agent's on_reconciled hook).
        record = await ezra.graph_store.get(FLEET_GRAPH)
        if record is not None:
            print("\n=== AGENT TRUST (post-reconciliation, 'tyres') ===")
            for reg in record.active_agents:
                print(f"   {reg.agent_id}: {reg.trust_scores.get('tyres')}")

        # Emit the enriched dashboard snapshot between sentinels so it can be
        # lifted straight out of the GKE Job logs and baked into the web dashboard.
        import json

        snapshot = await capture_snapshot(ezra, result)
        print(f"\n{SNAPSHOT_BEGIN}")
        print(json.dumps(snapshot, indent=2, default=str))
        print(SNAPSHOT_END)
    finally:
        await ezra.aclose()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(_main())
