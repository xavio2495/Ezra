"""Offline in-memory runtime for the examples — no Atlas/Redis/Qdrant/Gemini.

``build_offline_ezra()`` returns a fully-wired :class:`Ezra` backed by in-memory
stores (fakeredis hot tier, in-memory Qdrant warm tier, in-memory belief /
semantic / graph / branch stores), a deterministic stand-in LLM, and a simple
keyword contradiction checker. Every example's ``run(ezra)`` works the same
against this or against ``Ezra.from_env()`` — only the wiring differs.

The stand-ins (``DemoLLM``, ``KeywordChecker``) exist so the examples and their
tests run anywhere; production uses real Gemini + the two-pass NLI checker.
"""

from __future__ import annotations

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
from ezra_core.schemas.belief import Commitment, Contradiction
from ezra_core.session_graph import InMemorySessionGraphStore
from ezra_core.tiers.hot import HotTier
from ezra_core.tiers.warm import WarmTier


class DemoLLM:
    """Deterministic stand-in for a chat model.

    Returns ``[]`` for the learning agent's fact-extraction prompt (so no facts
    are invented offline) and a short, input-derived reply otherwise.
    """

    async def complete(self, messages, **kwargs) -> str:
        content = messages[-1]["content"] if messages else ""
        if "Extract durable" in content:
            return "[]"
        return f"[demo] Considered your request and recommend proceeding: {content[:80]}"


class KeywordEmbedder:
    """Tiny deterministic embedder for the warm tier (stable, hash-free)."""

    def encode(self, text: str) -> list[float]:
        vec = [0.0] * 8
        for ch in text.lower():
            vec[ord(ch) % 8] += 1.0
        return vec


class KeywordChecker:
    """Offline contradiction checker: flags two active commitments on the SAME
    topic whose claims differ. A deterministic stand-in for the real two-pass
    (embedding + NLI) checker so contradiction examples run without a model."""

    def check(self, *, new_claim, new_topic, new_agent_id, commitments) -> Contradiction | None:
        target = new_claim.strip().lower()
        for c in commitments:
            if c.superseded or c.redacted or c.topic != new_topic:
                continue
            if c.claim.strip().lower() != target:
                return Contradiction(
                    existing_commitment_id=c.id,
                    existing_agent_id=c.agent_id,
                    new_input_claim=new_claim,
                    new_agent_id=new_agent_id,
                    topic=new_topic,
                    similarity_score=1.0,
                    nli_confidence=1.0,
                    detected_at=datetime.now(timezone.utc),
                )
        return None


def build_offline_ezra(*, with_meta_agents: bool = True, checker: str | None = "keyword") -> Ezra:
    """Build an in-memory :class:`Ezra`. ``checker='keyword'`` enables the offline
    contradiction stand-in; pass ``None`` for pure write-back throughput."""
    graph_store = InMemorySessionGraphStore()
    belief = InMemoryBeliefStore()
    semantic = InMemorySemanticStore()
    llm = DemoLLM()
    branches = BranchManager(
        graph_store=graph_store, belief_store=belief, branch_store=InMemoryBranchStore()
    )
    chk = KeywordChecker() if checker == "keyword" else None
    learning = LearningMetaAgent(semantic, llm=llm) if with_meta_agents else None
    lifecycle = (
        LifecycleMetaAgent(graph_store, belief_store=belief) if with_meta_agents else None
    )
    return Ezra(
        settings=EzraSettings(),
        graph_store=graph_store,
        belief_store=belief,
        semantic_store=semantic,
        hot=HotTier(FakeAsyncRedis(decode_responses=True)),
        llm=llm,
        warm=WarmTier(AsyncQdrantClient(location=":memory:"), KeywordEmbedder()),
        checker=chk,
        branch_manager=branches,
        learning=learning,
        lifecycle=lifecycle,
    )


# -- small offline data sources for the federated-source examples ------------ #
class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def limit(self, n):
        return _Cursor(self._docs[:n])

    def __aiter__(self):
        async def gen():
            for d in self._docs:
                yield dict(d)

        return gen()


class _Collection:
    def __init__(self, docs):
        self._docs = list(docs)

    def find(self, _filter):
        return _Cursor(list(self._docs))


def demo_mongo_collection(docs) -> _Collection:
    """An async Mongo-like collection over in-memory docs (``find().limit()`` +
    ``async for``), so the MongoDB example runs without Atlas."""
    return _Collection(docs)


__all__ = [
    "build_offline_ezra",
    "demo_mongo_collection",
    "DemoLLM",
    "KeywordChecker",
    "KeywordEmbedder",
    "Commitment",
]
