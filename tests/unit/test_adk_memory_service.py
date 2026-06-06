"""EzraMemoryService — Ezra registered as an ADK BaseMemoryService.

Verifies it is a real ``BaseMemoryService``, that ``add_session_to_memory``
ingests ADK session events into Ezra's warm tier, and that ``search_memory``
returns matches as ADK ``MemoryEntry`` objects with ``google.genai`` content.
"""

import pytest

pytest.importorskip("google.adk")

from fakeredis import FakeAsyncRedis  # noqa: E402
from qdrant_client import AsyncQdrantClient  # noqa: E402

from ezra_core.adk_service import EzraMemoryService  # noqa: E402
from ezra_core.belief.branching import BranchManager, InMemoryBranchStore  # noqa: E402
from ezra_core.belief.store import InMemoryBeliefStore  # noqa: E402
from ezra_core.config import EzraSettings  # noqa: E402
from ezra_core.memory.semantic import InMemorySemanticStore  # noqa: E402
from ezra_core.runtime import Ezra  # noqa: E402
from ezra_core.session_graph import InMemorySessionGraphStore  # noqa: E402
from ezra_core.tiers.hot import HotTier  # noqa: E402
from ezra_core.tiers.warm import WarmTier  # noqa: E402


class _FakeEmbedder:
    def encode(self, text):
        v = [0.0] * 8
        for ch in text.lower():
            v[ord(ch) % 8] += 1.0
        return v


class _FakeLLM:
    async def complete(self, messages, **kwargs):
        return "ack"


def _ezra():
    graph_store = InMemorySessionGraphStore()
    belief = InMemoryBeliefStore()
    semantic = InMemorySemanticStore()
    return Ezra(
        settings=EzraSettings(),
        graph_store=graph_store,
        belief_store=belief,
        semantic_store=semantic,
        hot=HotTier(FakeAsyncRedis(decode_responses=True)),
        llm=_FakeLLM(),
        warm=WarmTier(AsyncQdrantClient(location=":memory:"), _FakeEmbedder()),
        branch_manager=BranchManager(
            graph_store=graph_store, belief_store=belief, branch_store=InMemoryBranchStore()
        ),
    )


def _session(events):
    from google.adk.sessions.session import Session

    return Session(id="s1", app_name="ezra-adk", user_id="team", events=events)


def _event(author, text):
    from google.adk.events.event import Event
    from google.genai import types

    return Event(author=author, content=types.Content(role="user", parts=[types.Part(text=text)]))


def test_memory_service_is_a_real_adk_base_memory_service():
    from google.adk.memory.base_memory_service import BaseMemoryService

    svc = EzraMemoryService(_ezra(), session_graph_id="g")
    assert isinstance(svc, BaseMemoryService)


async def test_add_session_then_search_roundtrips_through_ezra():
    mem = EzraMemoryService(_ezra(), session_graph_id="g")
    session = _session([
        _event("strategist", "tyre degradation is high in stint two"),
        _event("engineer", "fuel margin is comfortable"),
    ])
    await mem.add_session_to_memory(session)

    resp = await mem.search_memory(app_name="ezra-adk", user_id="team", query="tyre degradation")
    texts = " ".join(
        p.text for m in resp.memories for p in m.content.parts if p.text
    )
    assert "tyre degradation" in texts


async def test_search_returns_adk_memory_entries():
    from google.adk.memory.memory_entry import MemoryEntry

    mem = EzraMemoryService(_ezra(), session_graph_id="g")
    await mem.add_session_to_memory(_session([_event("a", "softs are graining")]))
    resp = await mem.search_memory(app_name="ezra-adk", user_id="team", query="softs")
    assert resp.memories and all(isinstance(m, MemoryEntry) for m in resp.memories)
    assert resp.memories[0].author == "a"


async def test_empty_query_against_empty_memory_is_safe():
    mem = EzraMemoryService(_ezra(), session_graph_id="g")
    resp = await mem.search_memory(app_name="ezra-adk", user_id="team", query="anything")
    assert resp.memories == []
