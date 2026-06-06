"""Append-only git-like history ops: revert_commitment + rewind_to_turn.

Guarantees under test:
  - revert drops a claim from the active set but keeps the full log;
  - rewind restores the live active set to the as-of-turn snapshot, including
    reactivating a pre-turn commitment that a post-turn commitment had superseded;
  - markers (type revert/rewind) never appear as active beliefs;
  - everything is append-only (get_all keeps every row) and the audit marker
    records what changed.
"""

from datetime import datetime, timezone

from ezra_core.belief.history import revert_commitment, rewind_to_turn
from ezra_core.belief.replay import reconstruct_state_at_turn, snapshot_now
from ezra_core.belief.store import InMemoryBeliefStore
from ezra_core.schemas.belief import Commitment

GID = "g"


def _c(cid, *, turn, claim, topic="tyres", agent="a"):
    return Commitment(
        id=cid,
        session_graph_id=GID,
        agent_id=agent,
        turn_index=turn,
        type="decision",
        claim=claim,
        topic=topic,
        created_at=datetime.now(timezone.utc),
    )


async def _active_claims(store):
    snap = await snapshot_now(store, GID)
    return {c.claim for c in snap.commitments}


# -- revert ---------------------------------------------------------------- #
async def test_revert_drops_claim_from_active_but_keeps_history():
    store = InMemoryBeliefStore()
    await store.append(_c("c1", turn=1, claim="run softs"))
    await store.append(_c("c2", turn=2, claim="box this lap"))

    marker = await revert_commitment(
        store, session_graph_id=GID, commitment_id="c1",
        by_agent="strategist", reason="bad call", turn_index=3,
    )

    assert await _active_claims(store) == {"box this lap"}  # c1 gone from active
    assert marker.type == "revert"
    assert marker.value["reverts"] == "c1"
    # history is intact: c1 still present (superseded), plus the marker.
    all_ids = {c.id for c in await store.get_all(GID)}
    assert {"c1", "c2", marker.id} <= all_ids
    assert (await store.get("c1")).superseded is True


async def test_revert_marker_is_not_itself_an_active_belief():
    store = InMemoryBeliefStore()
    await store.append(_c("c1", turn=1, claim="run softs"))
    await revert_commitment(
        store, session_graph_id=GID, commitment_id="c1",
        by_agent="x", reason="r", turn_index=2,
    )
    # the revert marker carries c1's topic but must NOT show up as active.
    active = await store.get_active(GID, topic="tyres")
    assert active == []


async def test_revert_missing_commitment_raises():
    store = InMemoryBeliefStore()
    import pytest

    with pytest.raises(KeyError):
        await revert_commitment(
            store, session_graph_id=GID, commitment_id="nope",
            by_agent="x", reason="r", turn_index=1,
        )


# -- rewind ---------------------------------------------------------------- #
async def test_rewind_undoes_post_turn_commitments():
    store = InMemoryBeliefStore()
    await store.append(_c("c1", turn=1, claim="plan A"))
    await store.append(_c("c2", turn=2, claim="plan B", topic="fuel"))
    await store.append(_c("c3", turn=5, claim="plan C", topic="aero"))

    result = await rewind_to_turn(
        store, session_graph_id=GID, turn=2, by_agent="director", reason="reset",
    )

    assert result.rewound_to_turn == 2
    assert result.superseded_ids == ["c3"]  # only the post-turn commitment
    assert await _active_claims(store) == {"plan A", "plan B"}
    # live active set now equals the as-of-turn-2 reconstruction.
    asof = await reconstruct_state_at_turn(store, GID, 2)
    assert {c.claim for c in asof.commitments} == await _active_claims(store)


async def test_rewind_reactivates_a_pre_turn_commitment_superseded_after():
    # A@2, then B@6 supersedes A. Rewind to 4 must bring A back (B didn't exist).
    store = InMemoryBeliefStore()
    await store.append(_c("A", turn=2, claim="mediums"))
    await store.append(_c("B", turn=6, claim="softs"))
    await store.supersede("A", "B")
    assert await _active_claims(store) == {"softs"}  # B active before rewind

    result = await rewind_to_turn(
        store, session_graph_id=GID, turn=4, by_agent="director", reason="undo B",
    )

    assert result.superseded_ids == ["B"]
    assert result.reactivated_ids == ["A"]
    assert await _active_claims(store) == {"mediums"}  # A restored, B undone
    # the marker records the prior link so the rewind is itself auditable.
    marker = await store.get(result.marker_id)
    assert marker.type == "rewind"
    assert marker.value["reactivated"] == {"A": "B"}


async def test_rewind_result_matches_reconstruct_for_the_reactivation_case():
    store = InMemoryBeliefStore()
    await store.append(_c("A", turn=2, claim="mediums"))
    await store.append(_c("B", turn=6, claim="softs"))
    await store.supersede("A", "B")

    await rewind_to_turn(
        store, session_graph_id=GID, turn=4, by_agent="d", reason="r",
    )
    asof = await reconstruct_state_at_turn(store, GID, 4)
    assert {c.claim for c in asof.commitments} == await _active_claims(store) == {"mediums"}


async def test_rewind_is_append_only_history_preserved():
    store = InMemoryBeliefStore()
    await store.append(_c("c1", turn=1, claim="a"))
    await store.append(_c("c2", turn=5, claim="b"))

    before = {c.id for c in await store.get_all(GID)}
    result = await rewind_to_turn(
        store, session_graph_id=GID, turn=1, by_agent="d", reason="r",
    )
    after = {c.id for c in await store.get_all(GID)}
    assert before < after  # only grew (marker added), nothing removed
    assert result.marker_id in after
