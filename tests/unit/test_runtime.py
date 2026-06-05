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
from ezra_core.runtime import Ezra
from ezra_core.schemas.belief import Contradiction
from ezra_core.session_graph import InMemorySessionGraphStore
from ezra_core.tiers.hot import HotTier
from ezra_core.tiers.warm import WarmTier


class FakeLLM:
    def __init__(self, reply="copy, boxing this lap"):
        self.reply = reply

    async def complete(self, messages, **kwargs):
        return self.reply


class FakeEmbedder:
    def encode(self, text):
        return [1.0, 0.0, 0.0] if "tyre" in text.lower() else [0.0, 0.0, 1.0]


class StubChecker:
    def __init__(self, result=None):
        self.result = result

    def check(self, **kwargs):
        return self.result


def _ezra(*, checker=None, closers=()):
    graph_store = InMemorySessionGraphStore()
    belief = InMemoryBeliefStore()
    semantic = InMemorySemanticStore()
    branches = BranchManager(
        graph_store=graph_store, belief_store=belief, branch_store=InMemoryBranchStore()
    )
    return Ezra(
        settings=EzraSettings(),
        graph_store=graph_store,
        belief_store=belief,
        semantic_store=semantic,
        hot=HotTier(FakeAsyncRedis(decode_responses=True)),
        llm=FakeLLM(),
        warm=WarmTier(AsyncQdrantClient(location=":memory:"), FakeEmbedder()),
        checker=checker,
        branch_manager=branches,
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
