from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from qdrant_client import AsyncQdrantClient

from ezra_core.schemas.memory import WarmSummary
from ezra_core.tiers.warm import WarmTier


class FakeEmbedder:
    """Clusters text onto one of three axes by keyword (deterministic)."""

    def encode(self, text: str):
        t = text.lower()
        if "tyre" in t:
            return [1.0, 0.0, 0.0]
        if "fuel" in t:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]


def _summary(text, *, topics, graph="g1", agent="strategist", when=None) -> WarmSummary:
    return WarmSummary(
        id=str(uuid4()),
        session_graph_id=graph,
        agent_id=agent,
        summary=text,
        topics=topics,
        created_at=when or datetime.now(timezone.utc),
    )


@pytest.fixture
def warm():
    return WarmTier(AsyncQdrantClient(location=":memory:"), FakeEmbedder())


async def test_recall_filters_by_scope(warm):
    await warm.add(_summary("tyre degradation high", topics=["tyres"]))
    await warm.add(_summary("fuel load marginal", topics=["fuel"]))

    hits = await warm.recall(
        session_graph_id="g1", query="tyre plan", scope_topics={"tyres"}, limit=5
    )
    assert [h.summary for h in hits] == ["tyre degradation high"]


async def test_recall_filters_by_session_graph(warm):
    await warm.add(_summary("tyre note A", topics=["tyres"], graph="g1"))
    await warm.add(_summary("tyre note B", topics=["tyres"], graph="g2"))

    hits = await warm.recall(
        session_graph_id="g1", query="tyre", scope_topics={"tyres"}, limit=5
    )
    assert [h.summary for h in hits] == ["tyre note A"]


async def test_untopiced_summary_visible_to_any_scope(warm):
    await warm.add(_summary("general standings update", topics=[]))
    hits = await warm.recall(
        session_graph_id="g1", query="anything", scope_topics={"tyres"}, limit=5
    )
    assert [h.summary for h in hits] == ["general standings update"]


async def test_ttl_excludes_expired(warm):
    old = datetime.now(timezone.utc) - timedelta(hours=48)
    await warm.add(_summary("stale tyre note", topics=["tyres"], when=old))
    hits = await warm.recall(
        session_graph_id="g1", query="tyre", scope_topics={"tyres"}, limit=5
    )
    assert hits == []


async def test_recall_empty_when_no_collection(warm):
    hits = await warm.recall(
        session_graph_id="g1", query="x", scope_topics={"tyres"}, limit=5
    )
    assert hits == []
