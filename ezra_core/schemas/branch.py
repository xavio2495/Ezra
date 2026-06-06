"""Branching replay models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Branch(BaseModel):
    branch_id: str
    parent_session_graph_id: str
    parent_turn: int
    created_at: datetime
    description: Optional[str] = None
    mutations: list[dict[str, Any]] = Field(default_factory=list)
    spawned_agents: list[dict[str, Any]] = Field(default_factory=list)
    forward_runs: list[dict[str, Any]] = Field(default_factory=list)


class BranchDiff(BaseModel):
    original_session_graph_id: str
    branch_id: str
    from_turn: int
    diverged_commitments: list[dict[str, Any]] = Field(default_factory=list)
    diverged_responses: list[dict[str, Any]] = Field(default_factory=list)
    diverged_mesh_results: list[dict[str, Any]] = Field(default_factory=list)
