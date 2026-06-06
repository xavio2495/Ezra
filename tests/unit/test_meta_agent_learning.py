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


class _ExtractLLM:
    """Fake LLM that returns a JSON fact list for the extraction prompt."""

    def __init__(self, reply):
        self.reply = reply

    async def complete(self, messages, **kwargs):
        return self.reply


async def test_extract_facts_parses_llm_json_into_archival_facts():
    llm = _ExtractLLM(
        '```json\n[{"subject":"soft tyre","predicate":"overheats",'
        '"object":"after lap 40","topics":["tyres","aero"],"confidence":0.9}]\n```'
    )
    agent = LearningMetaAgent(InMemorySemanticStore(), llm=llm)
    facts = await agent.extract_facts(
        user_id="team",
        source_graph_id="race-1",
        agent_id="tyre",
        user_input="how are the softs?",
        response="overheating after lap 40",
        scope_topics={"tyres"},
    )
    assert len(facts) == 1
    f = facts[0]
    assert (f.subject, f.predicate, f.object) == ("soft tyre", "overheats", "after lap 40")
    assert f.tier == "archival"
    assert f.source_session_graph_ids == ["race-1"]
    assert f.topics == ["tyres"]  # out-of-scope 'aero' filtered out


async def test_extract_facts_no_llm_returns_empty():
    agent = LearningMetaAgent(InMemorySemanticStore())  # no llm
    facts = await agent.extract_facts(
        user_id="team", source_graph_id="race-1", agent_id="x",
        user_input="hi", response="hello",
    )
    assert facts == []


async def test_run_after_turn_extracts_when_no_candidates_given():
    store = InMemorySemanticStore()
    llm = _ExtractLLM(
        '[{"subject":"front wing","predicate":"stock","object":"critical",'
        '"topics":["parts"],"confidence":0.95}]'
    )
    agent = LearningMetaAgent(store, llm=llm)
    report = await agent.run_after_turn(
        user_id="team",
        scope_topics={"parts"},
        source_graph_ids=["race-1"],
        user_input="wing stock?",
        response="2 of 4 needed",
        agent_id="parts",
    )
    assert len(report.persisted_fact_ids) == 1
    archived = await store.get_archival(
        user_id="team", scope_topics={"parts"}, source_graph_ids=["race-1"]
    )
    assert archived and archived[0].subject == "front wing"


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
