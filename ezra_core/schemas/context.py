"""Assembled-context models (router step 6 fills these). Minimal for now."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ContextSlotType(str, Enum):
    SYSTEM = "system"
    PINNED_BELIEF = "pinned_belief"
    WARM_SUMMARY = "warm_summary"
    HOT_TURN = "hot_turn"
    MESH_RESULT = "mesh_result"
    CURRENT_INPUT = "current_input"


class ContextSlot(BaseModel):
    slot_type: ContextSlotType
    content: str
    salience: float = Field(ge=0, le=1)
    token_cost: int = 0
    topics: list[str] = Field(default_factory=list)


class AssembledContext(BaseModel):
    session_graph_id: str
    agent_id: str
    slots: list[ContextSlot] = Field(default_factory=list)
    total_tokens: int = 0
