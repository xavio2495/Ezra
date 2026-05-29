"""Session graph and agent registration models (persisted state).

These are pure data models — no I/O. The runtime manager that creates, loads,
spawns into, and persists a session graph lives in ``ezra_core.session_graph``.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

MergeStrategy = Literal["last_write_wins", "highest_trust", "manual", "custom"]


class SessionGraphState(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class AgentRegistration(BaseModel):
    agent_id: str
    session_graph_id: str
    role: str = ""
    permission_scope: list[str] = Field(default_factory=list)
    spawned_at: datetime
    terminated_at: Optional[datetime] = None
    trust_scores: dict[str, float] = Field(default_factory=dict)  # topic -> trust


class SessionGraph(BaseModel):
    """Persisted state of one session graph. Imported as ``SessionGraphRecord``
    by the runtime module to avoid a name clash with the runtime manager."""

    session_graph_id: str
    state: SessionGraphState = SessionGraphState.ACTIVE
    created_at: datetime
    closed_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    description: str = ""
    merge_strategy: MergeStrategy = "last_write_wins"
    manual_resolution_timeout_seconds: int = 30
    inherits_from: list[str] = Field(default_factory=list)
    inherit_episodic: bool = False
    inherit_procedural: bool = True
    inherit_belief_history_queryable: bool = True
    archival_threshold_days: int = 90
    belief_retention_days: Optional[int] = None  # None = infinite
    meta_agent_overrides: dict[str, Any] = Field(default_factory=dict)
    active_agents: list[AgentRegistration] = Field(default_factory=list)
    terminated_agents: list[AgentRegistration] = Field(default_factory=list)
