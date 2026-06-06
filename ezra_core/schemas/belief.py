"""Belief store models — commitments, contradictions, resolutions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# Append-only audit markers (revert/rewind). They live in the belief log for
# history but are NOT active beliefs — excluded from get_active / snapshots.
MARKER_TYPES = frozenset({"revert", "rewind"})


class Commitment(BaseModel):
    id: str
    session_graph_id: str
    agent_id: str
    turn_index: int
    # "revert"/"rewind" are append-only audit markers written by the git-like
    # history ops (see ezra_core/belief/history.py), not agent-authored claims.
    type: Literal["fact", "decision", "calculation", "constraint", "revert", "rewind"]
    claim: str
    value: Optional[Any] = None
    topic: str
    trust_score: float = 1.0
    superseded: bool = False
    superseded_by: Optional[str] = None
    redacted: bool = False  # GDPR tombstone
    redaction_reason: Optional[str] = None
    created_at: datetime


class Contradiction(BaseModel):
    existing_commitment_id: str
    existing_agent_id: str
    new_input_claim: str
    new_agent_id: str
    topic: str
    similarity_score: float
    # Always "contradiction" — entailment/neutral are filtered out before this.
    nli_label: Literal["contradiction"] = "contradiction"
    nli_confidence: float = Field(ge=0, le=1)
    detected_at: datetime


class Resolution(BaseModel):
    decision: Literal["accept_new", "keep_existing", "escalate", "fallback"]
    fallback_strategy: Optional[Literal["last_write_wins", "highest_trust"]] = None
    resolved_commitment_id: Optional[str] = None
    merge_strategy_used: str = "custom"
    resolver_metadata: dict[str, Any] = Field(default_factory=dict)

    # Convenience constructors used by custom resolvers (see README).
    @classmethod
    def accept_new(cls, **meta: Any) -> "Resolution":
        return cls(decision="accept_new", resolver_metadata=meta)

    @classmethod
    def keep_existing(cls, **meta: Any) -> "Resolution":
        return cls(decision="keep_existing", resolver_metadata=meta)

    @classmethod
    def escalate(cls, **meta: Any) -> "Resolution":
        return cls(decision="escalate", resolver_metadata=meta)

    @classmethod
    def fallback_to(
        cls, strategy: Literal["last_write_wins", "highest_trust"], **meta: Any
    ) -> "Resolution":
        return cls(decision="fallback", fallback_strategy=strategy, resolver_metadata=meta)


class ContradictionEvent(BaseModel):
    """Surfaced to application callbacks in manual/custom reconciliation modes."""

    contradiction: Contradiction
    existing_claim: str
    existing_trust: float
    new_trust: float
    graph_state_snapshot_id: str


class BeliefSnapshot(BaseModel):
    """The (optionally scope-filtered) active belief state of a session graph,
    current or reconstructed as-of a prior turn. ``commitments`` excludes
    superseded and redacted entries."""

    session_graph_id: str
    as_of_turn: Optional[int] = None
    commitments: list[Commitment] = Field(default_factory=list)


class RewindResult(BaseModel):
    """Outcome of an append-only rewind (see ezra_core/belief/history.py): the
    audit marker, the post-turn commitments that were superseded, and the
    pre-turn commitments that were reactivated to restore the as-of-turn state."""

    session_graph_id: str
    rewound_to_turn: int
    marker_id: str
    superseded_ids: list[str] = Field(default_factory=list)
    reactivated_ids: list[str] = Field(default_factory=list)
