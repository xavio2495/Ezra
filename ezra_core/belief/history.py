"""Git-like history operations over the belief log — append-only and auditable.

Two operations, both of which NEVER delete: they supersede / reactivate existing
commitments and record a marker commitment (who, why, when) so the full audit
chain stays intact and replayable.

  * ``revert_commitment`` — git-revert semantics: drop one commitment from the
    active state (append a ``revert`` marker and supersede the target).
  * ``rewind_to_turn`` — undo every commitment made after a given turn on the
    LIVE graph, restoring the active set to its as-of-turn snapshot (append a
    single ``rewind`` marker, supersede the post-turn commitments, and reactivate
    any pre-turn commitment that only a now-undone commitment had superseded).

For an *exact* as-of-N snapshot in a *separate* graph, use
``BranchManager.branch_from(turn=N)`` instead — that forks a new graph; rewind
mutates the live graph in place.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ezra_core.belief.store import BeliefStore
from ezra_core.schemas.belief import Commitment, RewindResult


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def revert_commitment(
    store: BeliefStore,
    *,
    session_graph_id: str,
    commitment_id: str,
    by_agent: str,
    reason: str,
    turn_index: int,
) -> Commitment:
    """Revert a single commitment: append a ``revert`` marker and supersede the
    target so it leaves the active state. The target row is kept (superseded),
    so history and replay are unaffected. Raises ``KeyError`` if the target
    doesn't exist; a no-op-style marker is still avoided by checking first."""
    target = await store.get(commitment_id)
    if target is None or target.session_graph_id != session_graph_id:
        raise KeyError(f"commitment not found in {session_graph_id}: {commitment_id}")

    marker = Commitment(
        id=str(uuid4()),
        session_graph_id=session_graph_id,
        agent_id=by_agent,
        turn_index=turn_index,
        type="revert",
        claim=f"revert {commitment_id}: {reason}",
        value={"reverts": commitment_id, "reason": reason},
        topic=target.topic,
        created_at=_utcnow(),
    )
    await store.append(marker)
    if not target.superseded and not target.redacted:
        await store.supersede(commitment_id, marker.id)
    return marker


async def rewind_to_turn(
    store: BeliefStore,
    *,
    session_graph_id: str,
    turn: int,
    by_agent: str,
    reason: str,
) -> RewindResult:
    """Rewind the live graph to its as-of-``turn`` state (append-only).

    Supersedes every currently-active commitment with ``turn_index > turn`` and
    reactivates every pre-turn commitment that only a now-undone commitment had
    superseded — leaving the active set equal to ``reconstruct_state_at_turn``.
    All of it is recorded on one ``rewind`` marker (with the prior
    ``superseded_by`` links) so the rewind is itself auditable and reversible.
    """
    history = await store.get_all(session_graph_id)
    by_id = {c.id: c for c in history}

    marker_id = str(uuid4())

    # 1. Post-turn active commitments are undone.
    to_supersede = [
        c for c in history if c.turn_index > turn and not c.superseded and not c.redacted
    ]
    # 2. Pre-turn commitments superseded *only* by a now-undone commitment come back.
    undone_ids = {c.id for c in to_supersede}
    to_reactivate = [
        c
        for c in history
        if c.turn_index <= turn
        and c.superseded
        and c.superseded_by in undone_ids
        and not c.redacted
    ]

    marker = Commitment(
        id=marker_id,
        session_graph_id=session_graph_id,
        agent_id=by_agent,
        turn_index=turn,
        type="rewind",
        claim=f"rewind to turn {turn}: {reason}",
        value={
            "reason": reason,
            "superseded": [c.id for c in to_supersede],
            # prior links so the rewind can itself be undone / audited.
            "reactivated": {c.id: c.superseded_by for c in to_reactivate},
        },
        topic="",  # global marker; no single topic
        created_at=_utcnow(),
    )
    await store.append(marker)

    for c in to_supersede:
        await store.supersede(c.id, marker_id)
    for c in to_reactivate:
        await store.reactivate(c.id)

    return RewindResult(
        session_graph_id=session_graph_id,
        rewound_to_turn=turn,
        marker_id=marker_id,
        superseded_ids=[c.id for c in to_supersede],
        reactivated_ids=[c.id for c in to_reactivate],
    )
