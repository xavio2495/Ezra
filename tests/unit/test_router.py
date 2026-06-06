from datetime import datetime, timezone

import pytest
from fakeredis import aioredis
from qdrant_client import AsyncQdrantClient

from ezra_core.belief.store import InMemoryBeliefStore
from ezra_core.mesh.snowflake import SnowflakeConnector
from ezra_core.policy.engine import PolicyDeniedError, PolicyEngine
from ezra_core.router import Router
from ezra_core.schemas.belief import Commitment
from ezra_core.schemas.context import ContextSlotType
from ezra_core.schemas.memory import WarmSummary
from ezra_core.tiers.hot import HotTier
from ezra_core.tiers.warm import WarmTier


class FakeLLM:
    def __init__(self, reply="box this lap"):
        self.reply = reply
        self.last_messages = None

    async def complete(self, messages, **kwargs):
        self.last_messages = messages
        return self.reply


class FakeEmbedder:
    def encode(self, text):
        return [1.0, 0.0, 0.0] if "tyre" in text.lower() else [0.0, 0.0, 1.0]


def _agent(scope=("tyres",)):
    from ezra_core.schemas.session_graph import AgentRegistration

    return AgentRegistration(
        agent_id="strategist",
        session_graph_id="race-1",
        permission_scope=list(scope),
        spawned_at=datetime.now(timezone.utc),
    )


def _commit(claim, topic):
    return Commitment(
        id=f"{topic}-{claim[:4]}",
        session_graph_id="race-1",
        agent_id="eng",
        turn_index=1,
        type="decision",
        claim=claim,
        topic=topic,
        created_at=datetime.now(timezone.utc),
    )


async def _router(**overrides):
    hot = HotTier(aioredis.FakeRedis(decode_responses=True), max_turns=8)
    beliefs = InMemoryBeliefStore()
    llm = FakeLLM()
    router = Router(hot=hot, belief_store=beliefs, llm=llm, **overrides)
    return router, hot, beliefs, llm


async def test_run_turn_assembles_scope_filtered_beliefs_and_calls_llm():
    router, hot, beliefs, llm = await _router()
    await beliefs.append(_commit("start on softs", "tyres"))
    await beliefs.append(_commit("fuel margin is tight", "fuel"))  # out of scope

    result = await router.run_turn(
        agent=_agent(["tyres"]), user_input="what's the strategy?", system_prompt="You are race strategy."
    )

    assert result.response == "box this lap"
    slot_types = {s.slot_type for s in result.context.slots}
    assert ContextSlotType.SYSTEM in slot_types
    assert ContextSlotType.PINNED_BELIEF in slot_types
    assert ContextSlotType.CURRENT_INPUT in slot_types

    belief_text = " ".join(
        s.content for s in result.context.slots if s.slot_type == ContextSlotType.PINNED_BELIEF
    )
    assert "start on softs" in belief_text
    assert "fuel margin" not in belief_text  # scope filtered out

    # The LLM saw the pinned belief in its system message.
    assert "start on softs" in llm.last_messages[0]["content"]
    assert llm.last_messages[1] == {"role": "user", "content": "what's the strategy?"}


async def test_run_turn_writes_back_to_hot_tier():
    router, hot, beliefs, llm = await _router()
    agent = _agent()
    await hot.append_turn("race-1", "strategist", {"input": "earlier", "response": "ack"})

    await router.run_turn(agent=agent, user_input="now what?")
    turns = await hot.get_turns("race-1", "strategist")
    assert len(turns) == 2
    assert turns[-1] == {"input": "now what?", "response": "box this lap"}


async def test_run_turn_with_warm_recall():
    warm = WarmTier(AsyncQdrantClient(location=":memory:"), FakeEmbedder())
    await warm.add(
        WarmSummary(
            id="11111111-1111-1111-1111-111111111111",
            session_graph_id="race-1",
            summary="tyre deg trending high in stint 2",
            topics=["tyres"],
            created_at=datetime.now(timezone.utc),
        )
    )
    router, *_ = await _router(warm=warm)
    result = await router.run_turn(agent=_agent(["tyres"]), user_input="tyre outlook?")
    warm_text = " ".join(
        s.content for s in result.context.slots if s.slot_type == ContextSlotType.WARM_SUMMARY
    )
    assert "tyre deg trending high" in warm_text


async def test_run_turn_emits_router_step_spans():
    from ezra_core.observability.tracer import EzraTracer

    tracer, exporter = EzraTracer.in_memory()
    router, *_ = await _router(tracer=tracer)
    await router.run_turn(agent=_agent(["tyres"]), user_input="status?")

    span_names = {s.name for s in exporter.get_finished_spans()}
    assert {"router.belief_check", "router.hydrate", "router.assemble",
            "router.llm", "router.write_back"} <= span_names


class _ExtractingLLM:
    """Returns JSON facts for the extraction prompt, a normal reply otherwise."""

    async def complete(self, messages, **kwargs):
        content = messages[-1]["content"] if messages else ""
        if "Extract durable" in content:
            return (
                '[{"subject":"soft tyre","predicate":"overheats",'
                '"object":"after lap 40","topics":["tyres"],"confidence":0.9}]'
            )
        return "box this lap"


async def _learning_router(tracer=None):
    from ezra_core.memory.semantic import InMemorySemanticStore
    from ezra_core.meta_agent.learning import LearningMetaAgent

    hot = HotTier(aioredis.FakeRedis(decode_responses=True), max_turns=8)
    beliefs = InMemoryBeliefStore()
    semantic = InMemorySemanticStore()
    llm = _ExtractingLLM()
    learning = LearningMetaAgent(semantic, llm=llm)
    router = Router(
        hot=hot, belief_store=beliefs, llm=llm, learning=learning, tracer=tracer
    )
    return router, semantic


async def test_run_turn_runs_learning_pass_and_persists_extracted_facts():
    router, semantic = await _learning_router()
    result = await router.run_turn(
        agent=_agent(["tyres"]), user_input="tyre status?", user_id="team-1"
    )
    assert result.learning_report is not None
    assert len(result.learning_report.persisted_fact_ids) == 1
    facts = await semantic.get_archival(
        user_id="team-1", scope_topics={"tyres"}, source_graph_ids=["race-1"]
    )
    assert facts and facts[0].subject == "soft tyre"


async def test_run_turn_skips_learning_without_user_id():
    router, semantic = await _learning_router()
    result = await router.run_turn(agent=_agent(["tyres"]), user_input="tyre status?")
    assert result.learning_report is None
    facts = await semantic.get_archival(
        user_id="team-1", scope_topics={"tyres"}, source_graph_ids=["race-1"]
    )
    assert facts == []


async def test_run_turn_emits_learning_span():
    from ezra_core.observability.tracer import EzraTracer

    tracer, exporter = EzraTracer.in_memory()
    router, _ = await _learning_router(tracer=tracer)
    await router.run_turn(agent=_agent(["tyres"]), user_input="status?", user_id="team-1")
    assert "meta.learning" in {s.name for s in exporter.get_finished_spans()}


async def test_run_turn_mesh_fetch_policy_denied():
    connector = SnowflakeConnector("wh.inventory", executor=lambda sql: [])
    router, *_ = await _router(policy=PolicyEngine(enabled=True), mesh=connector)

    with pytest.raises(PolicyDeniedError):
        await router.run_turn(
            agent=_agent(["tyres"]),
            user_input="check procurement",
            mesh_query="contracts",
            mesh_topics=["procurement"],  # not in scope
        )
