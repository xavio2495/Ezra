from datetime import datetime, timezone

from ezra_core.belief.replay import reconstruct_state_at_turn, snapshot_now
from ezra_core.belief.store import InMemoryBeliefStore
from ezra_core.schemas.belief import Commitment


def _c(cid: str, *, turn: int, topic: str = "tyres") -> Commitment:
    return Commitment(
        id=cid,
        session_graph_id="g1",
        agent_id="a",
        turn_index=turn,
        type="fact",
        claim=f"claim-{cid}",
        topic=topic,
        created_at=datetime.now(timezone.utc),
    )


async def _seed() -> InMemoryBeliefStore:
    store = InMemoryBeliefStore()
    # turn 3: original tyre call; turn 20: superseding tyre call
    await store.append(_c("orig", turn=3))
    await store.append(_c("super", turn=20))
    await store.supersede("orig", superseded_by="super")
    return store


async def test_supersession_is_time_aware():
    store = await _seed()

    # At turn 15 the superseding commitment doesn't exist yet → original active.
    at15 = await reconstruct_state_at_turn(store, "g1", 15)
    assert {c.id for c in at15.commitments} == {"orig"}
    assert at15.as_of_turn == 15

    # At turn 25 the supersession has happened → only the new one is active.
    at25 = await reconstruct_state_at_turn(store, "g1", 25)
    assert {c.id for c in at25.commitments} == {"super"}


async def test_reconstruct_excludes_future_turns():
    store = await _seed()
    at2 = await reconstruct_state_at_turn(store, "g1", 2)
    assert at2.commitments == []


async def test_reconstruct_excludes_redacted():
    store = await _seed()
    await store.redact("super", reason="gdpr")
    at25 = await reconstruct_state_at_turn(store, "g1", 25)
    # 'orig' is superseded-as-of-25, 'super' is redacted → empty.
    assert at25.commitments == []


async def test_snapshot_now_and_scope_filter():
    store = InMemoryBeliefStore()
    await store.append(_c("t", turn=1, topic="tyres"))
    await store.append(_c("f", turn=2, topic="fuel"))

    snap = await snapshot_now(store, "g1", scope_topics={"fuel"})
    assert {c.id for c in snap.commitments} == {"f"}
    assert snap.as_of_turn is None
