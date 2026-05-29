"""Federated query (mesh) result models with typed provenance."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    source: str
    synced_at: Optional[datetime] = None
    field_types: dict[str, str] = Field(default_factory=dict)
    confidence: float = 1.0
    # MongoDB has no query-time time-travel; Snowflake/BigQuery do. See connectors.
    time_travel_available: bool = False
    queried_at: datetime


class MeshResult(BaseModel):
    data: Any
    provenance: Provenance
    topics: list[str] = Field(default_factory=list)
    fetch_time_ms: Optional[float] = None
