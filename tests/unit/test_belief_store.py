from datetime import datetime, timezone

from ezra_core.belief.store import InMemoryBeliefStore
from ezra_core.schemas.belief import Commitment


def _c(cid: str, *, turn: int, topic: str = "tyres", graph: str = "g1") -> Commitment:
    return Commitment(
        id=cid,
        session_graph_id=graph,
        agent_id="a",
        turn_index=turn,
        type="fact",
        claim=f"claim-{cid}",
        topic=topic,
        created_at=datetime.now(timezone.utc),
    )


async def test_append_and_get_all_sorted_by_turn():
    store = InMemoryBeliefStore()
    await store.append(_c("b", turn=5))
    await store.append(_c("a", turn=1))
    all_c = await store.get_all("g1")
    assert [c.id for c in all_c] == ["a", "b"]


async def test_get_all_scoped_by_graph_and_turn():
    store = InMemoryBeliefStore()
    await store.append(_c("x", turn=2, graph="g1"))
    await store.append(_c("y", turn=9, graph="g1"))
    await store.append(_c("z", turn=2, graph="g2"))
    assert {c.id for c in await store.get_all("g1")} == {"x", "y"}
    assert {c.id for c in await store.get_all("g1", up_to_turn=5)} == {"x"}


async def test_active_excludes_superseded_and_redacted():
    store = InMemoryBeliefStore()
    await store.append(_c("old", turn=1))
    await store.append(_c("new", turn=2))
    await store.append(_c("secret", turn=3))
    await store.supersede("old", superseded_by="new")
    await store.redact("secret", reason="gdpr")

    active = await store.get_active("g1")
    assert {c.id for c in active} == {"new"}


async def test_active_filtered_by_topic():
    store = InMemoryBeliefStore()
    await store.append(_c("t", turn=1, topic="tyres"))
    await store.append(_c("f", turn=2, topic="fuel"))
    assert {c.id for c in await store.get_active("g1", topic="fuel")} == {"f"}
