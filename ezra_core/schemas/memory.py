"""Memory models — episodic, semantic, and procedural."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class EpisodicMemory(BaseModel):
    id: str
    session_graph_id: str
    agent_id: Optional[str] = None
    user_id: str
    timestamp: datetime
    summary: str
    topics: list[str] = Field(default_factory=list)
    full_turn_ids: list[str] = Field(default_factory=list)
    salience: float = Field(ge=0, le=1)


class SemanticFact(BaseModel):
    id: str
    user_id: str
    subject: str
    predicate: str
    object: str
    tier: Literal["core", "archival"] = "archival"
    topics: list[str] = Field(default_factory=list)
    access_count: int = 0
    confidence: float = Field(ge=0, le=1)
    # Vector embedding of "subject predicate object" — set on add when the store
    # has an embedder; powers per-turn archival recall by similarity (Atlas
    # ``$vectorSearch`` / in-memory cosine).
    embedding: Optional[list[float]] = None
    # which graphs first surfaced this fact (cross-graph inheritance tracking)
    source_session_graph_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    superseded_by: Optional[str] = None


class WarmSummary(BaseModel):
    """Compressed prior turn / topic summary held in the warm tier (Qdrant).
    ``id`` must be a UUID string (Qdrant point id)."""

    id: str
    session_graph_id: str
    agent_id: Optional[str] = None
    summary: str
    topics: list[str] = Field(default_factory=list)
    salience: float = Field(default=1.0, ge=0, le=1)
    created_at: datetime


class ProceduralRule(BaseModel):
    """Inferred behavioural rule, loaded by intent-pattern / scope match."""

    id: str
    user_id: str
    pattern: str  # intent pattern this rule applies to
    rule: str
    topics: list[str] = Field(default_factory=list)
    source_session_graph_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    created_at: datetime
