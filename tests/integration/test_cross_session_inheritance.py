"""Cross-graph inheritance + replay against a real Atlas cluster.

Skipped unless EZRA_MONGODB_URI is set. Exercises the Session-2 "done when":
graph A commits a fact at turn 5; graph B inherits_from=[A]; a new agent in B
loads the fact at spawn — and a replay reconstructs B-independent state.

Uses unique graph ids per run and deletes everything it writes.
"""

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("EZRA_MONGODB_URI"),
    reason="EZRA_MONGODB_URI not set — skipping Atlas integration test",
)


async def test_inheritance_and_replay_roundtrip():
    from datetime import datetime, timezone

    from ezra_core.belief.replay import reconstruct_state_at_turn
    from ezra_core.belief.store import MongoBeliefStore
    from ezra_core.memory.semantic import MongoSemanticStore
    from ezra_core.router import hydrate_at_agent_spawn, write_back
    from ezra_core.schemas.memory import SemanticFact
    from ezra_core.schemas.session_graph import AgentRegistration
    from ezra_core.schemas.session_graph import SessionGraph as SessionGraphRecord
    from ezra_core.tiers.cold import cold_client

    db = os.getenv("EZRA_MONGODB_DB", "ezra")
    client = cold_client(os.environ["EZRA_MONGODB_URI"])
    beliefs = MongoBeliefStore(client, db)
    semantic = MongoSemanticStore(client, db)

    suffix = uuid.uuid4().hex[:8]
    graph_a = f"it-A-{suffix}"
    graph_b = f"it-B-{suffix}"
    user = f"it-user-{suffix}"
    now = datetime.now(timezone.utc)

    fact = SemanticFact(
        id=f"it-fact-{suffix}",
        user_id=user,
        subject="medium tyre",
        predicate="optimal_window",
        object="laps 12-18",
        tier="core",
        topics=["tyres"],
        confidence=1.0,
        source_session_graph_ids=[graph_a],
        created_at=now,
        updated_at=now,
    )

    try:
        # Graph A commits a fact at turn 5 (belief log) + persists the core fact.
        commitment = await write_back(
            belief_store=beliefs,
            session_graph_id=graph_a,
            agent_id="strategist",
            turn_index=5,
            claim="medium tyre optimal window is laps 12-18",
            topic="tyres",
            semantic_store=semantic,
            semantic_facts=[fact],
        )

        # Graph B inherits from A; new agent loads A's core fact at spawn.
        graph_b_record = SessionGraphRecord(
            session_graph_id=graph_b,
            created_at=now,
            inherits_from=[graph_a],
        )
        agent = AgentRegistration(
            agent_id="strategist_b",
            session_graph_id=graph_b,
            permission_scope=["tyres"],
            spawned_at=now,
        )
        hydration = await hydrate_at_agent_spawn(
            graph=graph_b_record,
            agent=agent,
            user_id=user,
            semantic_store=semantic,
        )
        assert {f.id for f in hydration.inherited_core} == {fact.id}
        assert hydration.own_core == []  # nothing sourced from B yet

        # Belief history is NOT inherited: B's belief state stays clean.
        snap_b = await reconstruct_state_at_turn(beliefs, graph_b, 10)
        assert snap_b.commitments == []

        # ...but A's belief snapshot reproduces the turn-5 commitment.
        snap_a = await reconstruct_state_at_turn(beliefs, graph_a, 5)
        assert {c.id for c in snap_a.commitments} == {commitment.id}
    finally:
        await beliefs._c.delete_many({"session_graph_id": {"$in": [graph_a, graph_b]}})
        await semantic._c.delete_many({"user_id": user})
        await client.close()
