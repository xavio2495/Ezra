"""Memory models — episodic and semantic. Procedural is added with its store."""

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
    # which graphs first surfaced this fact (cross-graph inheritance tracking)
    source_session_graph_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    superseded_by: Optional[str] = None
