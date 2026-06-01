"""Federated query connectors. A connector translates agent intent into a
native query, executes it at the source, and returns a typed ``MeshResult`` with
provenance — the model never receives raw rows.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from ezra_core.schemas.mesh import MeshResult, Provenance


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BaseConnector(ABC):
    #: Whether this source supports query-time time-travel (MongoDB: no).
    time_travel_available: bool = False

    @abstractmethod
    async def fetch(
        self,
        query: str,
        agent_id: str,
        permission_scope: list[str],
        as_of: Optional[datetime] = None,
    ) -> MeshResult:
        """Translate intent → native query, execute, return a typed result."""

    def _provenance(
        self,
        *,
        source: str,
        field_types: Optional[dict[str, str]] = None,
        confidence: float = 1.0,
        synced_at: Optional[datetime] = None,
    ) -> Provenance:
        return Provenance(
            source=source,
            synced_at=synced_at,
            field_types=field_types or {},
            confidence=confidence,
            time_travel_available=self.time_travel_available,
            queried_at=_utcnow(),
        )
