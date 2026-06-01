from datetime import datetime, timezone

from ezra_core.memory.semantic import InMemorySemanticStore
from ezra_core.meta_agent.learning import LearningMetaAgent
from ezra_core.schemas.memory import SemanticFact
from ezra_core.schemas.session_graph import AgentRegistration


def _fact(fact_id, *, confidence=0.9, tier="archival", access_count=0, topics=("tyres",)):
    now = datetime.now(timezone.utc)
    return SemanticFact(
        id=fact_id,
        user_id="team",
        subject="FW-07",
        predicate="status",
        object="critical",
        tier=tier,
        topics=list(topics),
        access_count=access_count,
        confidence=confidence,
        source_session_graph_ids=["race-1"],
        created_at=now,
        updated_at=now,
    )


def _agent():
    return AgentRegistration(
        agent_id="parts",
        session_graph_id="race-1",
        permission_scope=["parts"],
        spawned_at=datetime.now(timezone.utc),
    )


def test_score_writes_drops_low_confidence():
    agent = LearningMetaAgent(InMemorySemanticStore(), write_confidence_threshold=0.5)
    kept = agent.score_writes([_fact("a", confidence=0.9), _fact("b", confidence=0.2)])
    assert [f.id for f in kept] == ["a"]


async def test_persist_writes_only_persists_confident_facts():
    store = InMemorySemanticStore()
    agent = LearningMetaAgent(store, write_confidence_threshold=0.5)
    persisted = await agent.persist_writes([_fact("a", confidence=0.9), _fact("b", confidence=0.1)])
    assert persisted == ["a"]
    assert await store.get("a") is not None
    assert await store.get("b") is None


async def test_promote_eligible_promotes_hot_archival_facts_to_core():
    store = InMemorySemanticStore()
    await store.add(_fact("hot", access_count=3))
    await store.add(_fact("cold", access_count=1))
    agent = LearningMetaAgent(store, promotion_access_count=3)

    promoted = await agent.promote_eligible(
        user_id="team", scope_topics={"tyres"}, source_graph_ids=["race-1"]
    )

    assert promoted == ["hot"]
    assert (await store.get("hot")).tier == "core"
    assert (await store.get("cold")).tier == "archival"


def test_damp_trust_moves_toward_target_but_does_not_swing():
    agent = LearningMetaAgent(InMemorySemanticStore(), trust_damping=0.2)
    # won: toward 1.0 — 0.8 + 0.2*(1-0.8) = 0.84
    assert agent.damp_trust(0.8, won=True) == 0.84
    # lost: toward 0.0 — 0.8 + 0.2*(0-0.8) = 0.64
    assert agent.damp_trust(0.8, won=False) == 0.64


def test_record_reconciliation_updates_registration_in_place():
    agent = LearningMetaAgent(InMemorySemanticStore(), trust_damping=0.2)
    reg = _agent()
    reg.trust_scores["parts"] = 0.8
    updated = agent.record_reconciliation(reg, "parts", won=True)
    assert updated == 0.84
    assert reg.trust_scores["parts"] == 0.84


async def test_run_after_turn_reports_writes_promotions_and_trust():
    store = InMemorySemanticStore()
    await store.add(_fact("hot", access_count=5))
    agent = LearningMetaAgent(store, promotion_access_count=3, trust_damping=0.2)
    reg = _agent()
    reg.trust_scores["parts"] = 0.9

    report = await agent.run_after_turn(
        user_id="team",
        scope_topics={"tyres", "parts"},
        source_graph_ids=["race-1"],
        fact_candidates=[_fact("new", confidence=0.95)],
        reconciliations=[(reg, "parts", True)],
    )

    assert report.persisted_fact_ids == ["new"]
    assert report.promoted_fact_ids == ["hot"]
    assert report.trust_updates == {"parts:parts": 0.92}
