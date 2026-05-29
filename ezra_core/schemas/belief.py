"""Belief store models — commitments, contradictions, resolutions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class Commitment(BaseModel):
    id: str
    session_graph_id: str
    agent_id: str
    turn_index: int
    type: Literal["fact", "decision", "calculation", "constraint"]
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
    merge_strategy_used: str
    resolver_metadata: dict[str, Any] = Field(default_factory=dict)


class ContradictionEvent(BaseModel):
    """Surfaced to application callbacks in manual/custom reconciliation modes."""

    contradiction: Contradiction
    existing_claim: str
    existing_trust: float
    new_trust: float
    graph_state_snapshot_id: str
