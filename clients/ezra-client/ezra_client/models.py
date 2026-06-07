"""Wire models for the Ezra REST surface — the typed objects the client returns.

These mirror the platform's pydantic schemas (``ezra_core.schemas.*``) so a remote
agent sees the same shapes it would in-process. They are intentionally vendored
(copied, not imported) so ``ezra-client`` stays a slim, standalone install with no
dependency on the heavy ``ezra-core`` runtime. A drift guard in the test suite
asserts field-parity with the platform schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class Commitment(BaseModel):
    id: str
    session_graph_id: str
    agent_id: str
    turn_index: int
    type: Literal["fact", "decision", "calculation", "constraint", "revert", "rewind"]
    claim: str
    value: Optional[Any] = None
    topic: str
    trust_score: float = 1.0
    superseded: bool = False
    superseded_by: Optional[str] = None
    redacted: bool = False
    redaction_reason: Optional[str] = None
    created_at: datetime


class Contradiction(BaseModel):
    existing_commitment_id: str
    existing_agent_id: str
    new_input_claim: str
    new_agent_id: str
    topic: str
    similarity_score: float
    nli_label: Literal["contradiction"] = "contradiction"
    nli_confidence: float = Field(ge=0, le=1)
    detected_at: datetime


class Resolution(BaseModel):
    decision: Literal["accept_new", "keep_existing", "escalate", "fallback"]
    fallback_strategy: Optional[Literal["last_write_wins", "highest_trust"]] = None
    resolved_commitment_id: Optional[str] = None
    merge_strategy_used: str = "custom"
    resolver_metadata: dict[str, Any] = Field(default_factory=dict)


class BeliefSnapshot(BaseModel):
    session_graph_id: str
    as_of_turn: Optional[int] = None
    commitments: list[Commitment] = Field(default_factory=list)


class RewindResult(BaseModel):
    session_graph_id: str
    rewound_to_turn: int
    marker_id: str
    superseded_ids: list[str] = Field(default_factory=list)
    reactivated_ids: list[str] = Field(default_factory=list)


class CommitResult(BaseModel):
    commitment: Commitment
    contradiction: Optional[Contradiction] = None
    resolution: Optional[Resolution] = None


class WarmSummary(BaseModel):
    id: str
    session_graph_id: str
    agent_id: Optional[str] = None
    summary: str
    topics: list[str] = Field(default_factory=list)
    salience: float = Field(default=1.0, ge=0, le=1)
    created_at: datetime


class Provenance(BaseModel):
    source: str
    synced_at: Optional[datetime] = None
    field_types: dict[str, str] = Field(default_factory=dict)
    confidence: float = 1.0
    time_travel_available: bool = False
    queried_at: datetime


class MeshResult(BaseModel):
    data: Any
    provenance: Provenance
    topics: list[str] = Field(default_factory=list)
    fetch_time_ms: Optional[float] = None


class Branch(BaseModel):
    branch_id: str
    parent_session_graph_id: str
    parent_turn: int
    created_at: datetime
    description: Optional[str] = None
    mutations: list[dict[str, Any]] = Field(default_factory=list)
    spawned_agents: list[dict[str, Any]] = Field(default_factory=list)
    forward_runs: list[dict[str, Any]] = Field(default_factory=list)


__all__ = [
    "Commitment",
    "Contradiction",
    "Resolution",
    "BeliefSnapshot",
    "RewindResult",
    "CommitResult",
    "WarmSummary",
    "Provenance",
    "MeshResult",
    "Branch",
]
