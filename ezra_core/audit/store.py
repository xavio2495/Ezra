"""Audit log store — the persisted activity feed (see schemas/audit.py).

Follows the platform storage pattern: an ``AuditLog`` Protocol with an in-memory
implementation for DB-free unit tests and a MongoDB implementation
(``audit_events`` collection) for real persistence. Append-only — events are
never mutated or deleted.
"""

from __future__ import annotations

from typing import Optional, Protocol

from pymongo import AsyncMongoClient

from ezra_core.schemas.audit import AuditEvent


class AuditLog(Protocol):
    """Persistence port for the append-only activity feed."""

    async def append(self, event: AuditEvent) -> None: ...
    async def get_for_graph(
        self, session_graph_id: str, *, limit: int = 100
    ) -> list[AuditEvent]: ...


class InMemoryAuditLog:
    """In-memory store for unit tests. Stores deep copies to avoid aliasing."""

    def __init__(self) -> None:
        self._items: list[AuditEvent] = []

    async def append(self, event: AuditEvent) -> None:
        self._items.append(event.model_copy(deep=True))

    async def get_for_graph(
        self, session_graph_id: str, *, limit: int = 100
    ) -> list[AuditEvent]:
        out = [
            e.model_copy(deep=True)
            for e in self._items
            if e.session_graph_id == session_graph_id
        ]
        out.sort(key=lambda e: e.created_at)
        return out[-limit:] if limit else out


def _strip(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


class MongoAuditLog:
    """MongoDB-backed activity feed (the real persistence)."""

    def __init__(
        self,
        client: AsyncMongoClient,
        db_name: str,
        collection: str = "audit_events",
    ) -> None:
        self._c = client[db_name][collection]

    async def append(self, event: AuditEvent) -> None:
        doc = event.model_dump(mode="json")
        doc["_id"] = event.id
        await self._c.replace_one({"_id": event.id}, doc, upsert=True)

    async def get_for_graph(
        self, session_graph_id: str, *, limit: int = 100
    ) -> list[AuditEvent]:
        # Newest-first from Mongo (so limit keeps the most recent), returned oldest-first.
        cursor = self._c.find({"session_graph_id": session_graph_id}).sort(
            "created_at", -1
        )
        if limit:
            cursor = cursor.limit(limit)
        out = [AuditEvent.model_validate(_strip(d)) async for d in cursor]
        out.sort(key=lambda e: e.created_at)
        return out
