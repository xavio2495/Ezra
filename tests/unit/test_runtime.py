"""Composition-root tests for ``Ezra`` — DB-/network-/torch-free.

Builds the runtime from in-memory components (the plain constructor, not
``from_settings``) and checks that it wires a working ``EzraService`` per agent:
``spawn_agent`` registers the agent on the graph, ``complete`` runs a turn through
the real router with a fake LLM, ``belief_check`` reaches the injected checker,
and ``aclose`` drains the closers.
"""

from datetime import datetime, timezone

from fakeredis import FakeAsyncRedis
from qdrant_client import AsyncQdrantClient

from ezra_core.belief.branching import BranchManager, InMemoryBranchStore
from ezra_core.belief.store import InMemoryBeliefStore
from ezra_core.config import EzraSettings
from ezra_core.memory.semantic import InMemorySemanticStore
from ezra_core.meta_agent.learning import LearningMetaAgent
from ezra_core.meta_agent.lifecycle import LifecycleMetaAgent
from ezra_core.runtime import Ezra
from ezra_core.schemas.belief import Contradiction
from ezra_core.session_graph import InMemorySessionGraphStore
from ezra_core.tiers.hot import HotTier
from ezra_core.tiers.warm import WarmTier


class FakeLLM:
    def __init__(self, reply="copy, boxing this lap"):
        self.reply = reply

    async def complete(self, messages, **kwargs):
        content = messages[-1]["content"] if messages else ""
        if "Extract durable" in content:
            return (
                '[{"subject":"soft tyre","predicate":"overheats",'
                '"object":"after lap 40","topics":["tyres"],"confidence":0.9}]'
            )
        return self.reply


class FakeEmbedder:
    def encode(self, text):
        return [1.0, 0.0, 0.0] if "tyre" in text.lower() else [0.0, 0.0, 1.0]


class StubChecker:
    def __init__(self, result=None):
        self.result = result

    def check(self, **kwargs):
        return self.result


def _ezra(*, checker=None, closers=(), with_meta_agents=False):
    graph_store = InMemorySessionGraphStore()
    belief = InMemoryBeliefStore()
    semantic = InMemorySemanticStore()
    llm = FakeLLM()
    branches = BranchManager(
        graph_store=graph_store, belief_store=belief, branch_store=InMemoryBranchStore()
    )
    learning = LearningMetaAgent(semantic, llm=llm) if with_meta_agents else None
    lifecycle = LifecycleMetaAgent(graph_store, belief_store=belief) if with_meta_agents else None
    return Ezra(
        settings=EzraSettings(),
        graph_store=graph_store,
        belief_store=belief,
        semantic_store=semantic,
        hot=HotTier(FakeAsyncRedis(decode_responses=True)),
        llm=llm,
        warm=WarmTier(AsyncQdrantClient(location=":memory:"), FakeEmbedder()),
        checker=checker,
        branch_manager=branches,
        learning=learning,
        lifecycle=lifecycle,
        closers=closers,
    )


async def test_spawn_agent_registers_on_graph_and_completes_a_turn():
    ezra = _ezra()
    graph = await ezra.create_session_graph(
        session_graph_id="race-1", description="Monaco", merge_strategy="highest_trust"
    )
    svc = await ezra.spawn_agent(graph, agent_id="strategist", permission_scope=["tyres"])

    # The agent is registered on the persisted graph record.
    assert [a.agent_id for a in graph.active_agents] == ["strategist"]

    # complete() runs the real 8-step router and returns the fake LLM reply.
    result = await svc.complete("what tyre for the final stint?", system_prompt="You strategise.")
    assert result.response == "copy, boxing this lap"
    assert result.agent_id == "strategist"


async def test_committed_belief_is_visible_to_a_second_agent_in_scope():
    ezra = _ezra()
    graph = await ezra.create_session_graph(session_graph_id="race-1")
    a = await ezra.spawn_agent(graph, agent_id="tyre", permission_scope=["tyres"])
    b = await ezra.spawn_agent(graph, agent_id="strategist", permission_scope=["tyres"])

    await a.write_back("softs are overheating", "tyres", turn_index=1)
    snap = await b.belief_snapshot()
    assert "softs are overheating" in {c.claim for c in snap.commitments}


async def test_belief_check_reaches_injected_checker():
    contradiction = Contradiction(
        existing_commitment_id="c1",
        existing_agent_id="tyre",
        new_input_claim="run mediums",
        new_agent_id="strategist",
        topic="tyres",
        similarity_score=0.9,
        nli_confidence=0.88,
        detected_at=datetime.now(timezone.utc),
    )
    ezra = _ezra(checker=StubChecker(contradiction))
    graph = await ezra.create_session_graph(session_graph_id="race-1")
    svc = await ezra.spawn_agent(graph, agent_id="strategist", permission_scope=["tyres"])
    assert await svc.belief_check("run mediums", "tyres") is contradiction


async def test_on_contradiction_decorator_drives_manual_reconciliation():
    contradiction = Contradiction(
        existing_commitment_id="c1",
        existing_agent_id="tyre",
        new_input_claim="run mediums",
        new_agent_id="strategist",
        topic="tyres",
        similarity_score=0.9,
        nli_confidence=0.88,
        detected_at=datetime.now(timezone.utc),
    )
    ezra = _ezra(checker=StubChecker(contradiction))

    seen = {}

    @ezra.on_contradiction
    async def resolve(event):
        seen["topic"] = event.contradiction.topic
        return "keep_existing"  # manual operator keeps the existing claim

    graph = await ezra.create_session_graph(
        session_graph_id="race-1", merge_strategy="manual"
    )
    svc = await ezra.spawn_agent(graph, agent_id="strategist", permission_scope=["tyres"])

    result = await svc.commit("run mediums", "tyres", turn_index=2)

    # The callback was invoked and its decision drove the resolution.
    assert seen["topic"] == "tyres"
    assert result.resolution is not None
    assert result.resolution.decision == "keep_existing"
    assert result.resolution.merge_strategy_used == "manual"


async def test_manual_mode_without_callback_falls_back():
    contradiction = Contradiction(
        existing_commitment_id="c1",
        existing_agent_id="tyre",
        new_input_claim="run mediums",
        new_agent_id="strategist",
        topic="tyres",
        similarity_score=0.9,
        nli_confidence=0.88,
        detected_at=datetime.now(timezone.utc),
    )
    ezra = _ezra(checker=StubChecker(contradiction))  # no @on_contradiction registered
    graph = await ezra.create_session_graph(
        session_graph_id="race-1", merge_strategy="manual"
    )
    svc = await ezra.spawn_agent(graph, agent_id="strategist", permission_scope=["tyres"])

    result = await svc.commit("run mediums", "tyres", turn_index=2)
    assert result.resolution.merge_strategy_used == "manual_no_callback_fallback"


async def test_spawn_agent_with_user_id_runs_learning_and_persists_facts():
    ezra = _ezra(with_meta_agents=True)
    graph = await ezra.create_session_graph(session_graph_id="race-1")
    svc = await ezra.spawn_agent(
        graph, agent_id="tyre", permission_scope=["tyres"], user_id="team-1"
    )

    result = await svc.complete("how are the softs holding up?")
    assert result.learning_report is not None
    assert len(result.learning_report.persisted_fact_ids) == 1

    facts = await ezra.semantic_store.get_archival(
        user_id="team-1", scope_topics={"tyres"}, source_graph_ids=["race-1"]
    )
    assert facts and facts[0].subject == "soft tyre"


async def test_run_lifecycle_tick_closes_idle_graph():
    ezra = _ezra(with_meta_agents=True)
    graph = await ezra.create_session_graph(session_graph_id="race-1")
    await ezra.spawn_agent(graph, agent_id="tyre", permission_scope=["tyres"])
    await graph.terminate_agent("tyre")

    report = await ezra.run_lifecycle_tick("race-1")
    assert report is not None and report.transition == "closed"


async def test_run_lifecycle_tick_noop_without_lifecycle_agent():
    ezra = _ezra()  # no meta-agents wired
    await ezra.create_session_graph(session_graph_id="race-1")
    assert await ezra.run_lifecycle_tick("race-1") is None


class DynChecker:
    """Flags a contradiction iff an active commitment on the topic differs."""

    def check(self, *, new_claim, new_topic, new_agent_id, commitments):
        for c in commitments:
            if c.topic == new_topic and c.claim != new_claim:
                return Contradiction(
                    existing_commitment_id=c.id,
                    existing_agent_id=c.agent_id,
                    new_input_claim=new_claim,
                    new_agent_id=new_agent_id,
                    topic=new_topic,
                    similarity_score=0.9,
                    nli_confidence=0.9,
                    detected_at=datetime.now(timezone.utc),
                )
        return None


async def test_live_reconciliation_damps_trust_via_learning():
    ezra = _ezra(checker=DynChecker(), with_meta_agents=True)
    graph = await ezra.create_session_graph(
        session_graph_id="race-1", merge_strategy="highest_trust"
    )
    a = await ezra.spawn_agent(graph, agent_id="tyre", permission_scope=["tyres"])
    b = await ezra.spawn_agent(graph, agent_id="strategist", permission_scope=["tyres"])
    for reg in graph.active_agents:
        reg.trust_scores["tyres"] = {"tyre": 0.95, "strategist": 0.80}[reg.agent_id]
    await ezra.graph_store.save(graph.record)

    await a.commit("run mediums", "tyres", turn_index=1)
    out = await b.commit("run softs", "tyres", turn_index=2)
    assert out.contradiction is not None
    assert out.resolution.decision == "keep_existing"  # tyre 0.95 beats strategist 0.80

    trust = {r.agent_id: r.trust_scores["tyres"] for r in graph.active_agents}
    assert trust["tyre"] == 0.96  # winner damped toward 1.0
    assert trust["strategist"] == 0.64  # loser damped toward 0.0


async def test_aclose_drains_closers():
    closed = []

    class Closer:
        def __init__(self, name):
            self.name = name

        async def aclose(self):
            closed.append(self.name)

    ezra = _ezra(closers=(Closer("redis"), Closer("qdrant")))
    await ezra.aclose()
    assert closed == ["redis", "qdrant"]
