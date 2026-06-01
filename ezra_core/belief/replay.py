"""Replay — reconstruct the active belief state as it stood at any prior turn.

A commitment is *active as-of turn N* when:
  - its ``turn_index`` is <= N, and
  - it is not redacted, and
  - it was not yet superseded as-of N — i.e. the commitment that supersedes it
    (``superseded_by``) either does not exist or has ``turn_index`` > N.

This makes supersession time-aware: a fact superseded at turn 20 is still active
in a snapshot reconstructed at turn 15.
"""

from __future__ import annotations

from typing import Optional

from ezra_core.belief.store import BeliefStore
from ezra_core.schemas.belief import BeliefSnapshot, Commitment
from ezra_core.scope import filter_by_scope


def _commitment_topics(c: Commitment) -> list[str]:
    # Commitments carry a single ``topic``; adapt to the topic-list scope filter.
    return [c.topic]


async def reconstruct_state_at_turn(
    store: BeliefStore,
    session_graph_id: str,
    turn: int,
    *,
    scope_topics: Optional[set[str]] = None,
) -> BeliefSnapshot:
    history = await store.get_all(session_graph_id, up_to_turn=turn)
    present_ids = {c.id for c in history}

    active: list[Commitment] = []
    for c in history:
        if c.redacted:
            continue
        # Superseded only counts if the superseding commitment also exists as-of N.
        if c.superseded_by is not None and c.superseded_by in present_ids:
            continue
        active.append(c)

    if scope_topics is not None:
        active = [
            c for c in active if filter_by_scope([_TopicView(c)], scope_topics)
        ]

    return BeliefSnapshot(
        session_graph_id=session_graph_id, as_of_turn=turn, commitments=active
    )


async def snapshot_now(
    store: BeliefStore,
    session_graph_id: str,
    *,
    scope_topics: Optional[set[str]] = None,
) -> BeliefSnapshot:
    """Current active belief state (no time travel)."""
    active = await store.get_active(session_graph_id)
    if scope_topics is not None:
        active = [c for c in active if filter_by_scope([_TopicView(c)], scope_topics)]
    return BeliefSnapshot(
        session_graph_id=session_graph_id, as_of_turn=None, commitments=active
    )


class _TopicView:
    """Adapts a Commitment's single ``topic`` to the ``.topics`` list that
    ``filter_by_scope`` expects, without mutating the schema."""

    __slots__ = ("topics",)

    def __init__(self, commitment: Commitment) -> None:
        self.topics = _commitment_topics(commitment)
