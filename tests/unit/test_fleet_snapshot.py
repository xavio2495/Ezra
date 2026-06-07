"""Offline test for the dashboard snapshot capture (``fleet.capture_snapshot``).

The live fleet itself needs real ADK + Gemini, but ``capture_snapshot`` just reads
back the runtime state a run leaves behind. So we build an in-memory ``Ezra``,
spawn the real fleet roles, plant a realistic belief log (a superseded claim + its
winner) + hot-tier turns, hand it a ``FleetResult`` shaped like the live events,
and assert the snapshot the web ``/dashboard`` is baked from.
"""

from datetime import datetime, timezone

from demo.f1_race_weekend.adk_runtime.fleet import (
    FLEET_GRAPH,
    FLEET_ROLES,
    FleetResult,
    capture_snapshot,
)
from demo.f1_race_weekend.agents.roles import role_by_id
from examples._harness import build_offline_ezra
from ezra_core.schemas.belief import Commitment


def _commit(agent, topic, claim, turn, *, superseded=False, superseded_by=None, trust=1.0):
    return Commitment(
        id=f"{agent}-{topic}-{turn}",
        session_graph_id=FLEET_GRAPH,
        agent_id=agent,
        turn_index=turn,
        type="decision",
        claim=claim,
        topic=topic,
        trust_score=trust,
        superseded=superseded,
        superseded_by=superseded_by,
        created_at=datetime.now(timezone.utc),
    )


async def _seeded_fleet():
    ezra = build_offline_ezra()
    graph = await ezra.create_session_graph(
        session_graph_id=FLEET_GRAPH, description="snapshot test"
    )
    for role_id in FLEET_ROLES:
        role = role_by_id(role_id)
        await ezra.spawn_agent(
            graph,
            agent_id=role.agent_id,
            permission_scope=role.permission_scope,
            role=role.role,
        )
    for reg in graph.active_agents:
        if reg.agent_id == "tyre_engineer":
            reg.trust_scores["tyres"] = 0.95
        elif reg.agent_id == "race_strategy":
            reg.trust_scores["tyres"] = 0.80
    await ezra.graph_store.save(graph.record)

    # Belief log: race_strategy's softs lost to tyre_engineer's mediums on 'tyres'.
    await ezra.belief_store.append(
        _commit("race_strategy", "tyres", "Start on softs.", 1,
                superseded=True, superseded_by="tyre_engineer-tyres-2", trust=0.80)
    )
    await ezra.belief_store.append(
        _commit("tyre_engineer", "tyres", "Start on mediums.", 2, trust=0.95)
    )
    await ezra.belief_store.append(
        _commit("weather_model", "weather", "Dry through lights-out.", 1)
    )
    for agent in ("race_strategy", "tyre_engineer"):
        await ezra.hot.append_turn(FLEET_GRAPH, agent, {"response": "...", "committed": []})
    return ezra


def _result():
    return FleetResult(
        graph_id=FLEET_GRAPH,
        contradictions=[{
            "kind": "contradiction", "topic": "tyres",
            "new_agent": "tyre_engineer", "with_agent": "race_strategy",
            "similarity": 0.86, "nli_confidence": 0.97,
            "decision": "accept_new", "strategy": "highest_trust",
        }],
        federated_fetches=[{
            "kind": "fetch", "agent": "race_strategy",
            "source": "snowflake:EZRA.PUBLIC.RACE_RESULTS",
            "time_travel_available": True, "rows": 100,
        }],
        denial={"agent": "logistics", "denied_topic": "aero",
                "scope": ["parts", "supplier", "calendar"]},
        branch_diff={"diverged": [{"topic": "tyres", "only_in_original": [],
                                   "only_in_branch": ["wets called at lap 43"]}]},
        final_beliefs=[],
    )


async def test_snapshot_agents_carry_scope_trust_and_commit_status():
    ezra = await _seeded_fleet()
    try:
        snap = await capture_snapshot(ezra, _result())
    finally:
        await ezra.aclose()

    assert snap["meta"]["graph_id"] == FLEET_GRAPH
    assert len(snap["agents"]) == len(FLEET_ROLES)
    by_id = {a["id"]: a for a in snap["agents"]}
    assert by_id["race_strategy"]["scope"] == ["strategy", "tyres"]
    assert by_id["race_strategy"]["committed"] is True
    assert by_id["race_strategy"]["trust_tyres"] == 0.80
    assert by_id["tyre_engineer"]["trust_tyres"] == 0.95
    # aero_rd committed nothing in this seeded log.
    assert by_id["aero_rd"]["committed"] is False


async def test_snapshot_tiers_and_beliefs_reflect_the_real_log():
    ezra = await _seeded_fleet()
    try:
        snap = await capture_snapshot(ezra, _result())
    finally:
        await ezra.aclose()

    tiers = snap["tiers"]
    assert tiers["cold_commitments"] == 3
    assert tiers["active_beliefs"] == 2
    assert tiers["superseded_beliefs"] == 1
    assert tiers["hot_turns"] == 2

    softs = next(b for b in snap["beliefs"] if b["claim"] == "Start on softs.")
    assert softs["superseded"] is True and softs["active"] is False
    mediums = next(b for b in snap["beliefs"] if b["claim"] == "Start on mediums.")
    assert mediums["active"] is True


async def test_snapshot_reconciliation_branch_fetch_denial_passthrough():
    ezra = await _seeded_fleet()
    try:
        snap = await capture_snapshot(ezra, _result())
    finally:
        await ezra.aclose()

    rec = snap["reconciliation"]
    assert rec["winner"] == "tyre_engineer" and rec["loser"] == "race_strategy"
    assert rec["winner_trust"] == 0.95 and rec["loser_trust"] == 0.80
    assert rec["similarity"] == 0.86 and rec["nli_confidence"] == 0.97

    assert snap["federated_fetches"][0]["source"].startswith("snowflake:")
    assert snap["denial"]["denied_topic"] == "aero"
    assert snap["branch"]["diverged"][0]["topic"] == "tyres"
