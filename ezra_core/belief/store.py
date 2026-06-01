"""Belief store — append-only commitment log with supersession + GDPR tombstones.

The log is append-only: commitments are never deleted. ``supersede`` and
``redact`` flip flags on an existing record (supersession chain / tombstone),
they do not remove it — the audit chain stays intact.

Follows the Session 1 storage pattern: a ``BeliefStore`` Protocol with an
in-memory implementation for DB-free unit tests and a MongoDB implementation
for real persistence.
"""

from __future__ import annotations

from typing import Optional, Protocol

from pymongo import AsyncMongoClient

from ezra_core.schemas.belief import Commitment


class BeliefStore(Protocol):
    """Persistence port for the append-only commitment log."""

    async def append(self, commitment: Commitment) -> None: ...
    async def get(self, commitment_id: str) -> Optional[Commitment]: ...
    async def get_all(
        self, session_graph_id: str, *, up_to_turn: Optional[int] = None
    ) -> list[Commitment]: ...
    async def get_active(
        self, session_graph_id: str, *, topic: Optional[str] = None
    ) -> list[Commitment]: ...
    async def supersede(self, commitment_id: str, superseded_by: str) -> None: ...
    async def redact(self, commitment_id: str, reason: str) -> None: ...


class InMemoryBeliefStore:
    """In-memory store for unit tests. Stores deep copies to avoid aliasing."""

    def __init__(self) -> None:
        self._items: dict[str, Commitment] = {}
        self._order: list[str] = []

    async def append(self, commitment: Commitment) -> None:
        if commitment.id not in self._items:
            self._order.append(commitment.id)
        self._items[commitment.id] = commitment.model_copy(deep=True)

    async def get(self, commitment_id: str) -> Optional[Commitment]:
        c = self._items.get(commitment_id)
        return c.model_copy(deep=True) if c is not None else None

    async def get_all(
        self, session_graph_id: str, *, up_to_turn: Optional[int] = None
    ) -> list[Commitment]:
        out = [
            self._items[cid].model_copy(deep=True)
            for cid in self._order
            if self._items[cid].session_graph_id == session_graph_id
            and (up_to_turn is None or self._items[cid].turn_index <= up_to_turn)
        ]
        out.sort(key=lambda c: c.turn_index)
        return out

    async def get_active(
        self, session_graph_id: str, *, topic: Optional[str] = None
    ) -> list[Commitment]:
        return [
            c
            for c in await self.get_all(session_graph_id)
            if not c.superseded
            and not c.redacted
            and (topic is None or c.topic == topic)
        ]

    async def supersede(self, commitment_id: str, superseded_by: str) -> None:
        c = self._items.get(commitment_id)
        if c is not None:
            c.superseded = True
            c.superseded_by = superseded_by

    async def redact(self, commitment_id: str, reason: str) -> None:
        c = self._items.get(commitment_id)
        if c is not None:
            c.redacted = True
            c.redaction_reason = reason


def _strip(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


class MongoBeliefStore:
    """MongoDB-backed commitment log (the real persistence)."""

    def __init__(
        self,
        client: AsyncMongoClient,
        db_name: str,
        collection: str = "commitments",
    ) -> None:
        self._c = client[db_name][collection]

    async def append(self, commitment: Commitment) -> None:
        doc = commitment.model_dump(mode="json")
        doc["_id"] = commitment.id
        await self._c.replace_one({"_id": commitment.id}, doc, upsert=True)

    async def get(self, commitment_id: str) -> Optional[Commitment]:
        doc = await self._c.find_one({"_id": commitment_id})
        return Commitment.model_validate(_strip(doc)) if doc is not None else None

    async def get_all(
        self, session_graph_id: str, *, up_to_turn: Optional[int] = None
    ) -> list[Commitment]:
        query: dict = {"session_graph_id": session_graph_id}
        if up_to_turn is not None:
            query["turn_index"] = {"$lte": up_to_turn}
        cursor = self._c.find(query).sort("turn_index", 1)
        return [Commitment.model_validate(_strip(d)) async for d in cursor]

    async def get_active(
        self, session_graph_id: str, *, topic: Optional[str] = None
    ) -> list[Commitment]:
        query: dict = {
            "session_graph_id": session_graph_id,
            "superseded": False,
            "redacted": False,
        }
        if topic is not None:
            query["topic"] = topic
        cursor = self._c.find(query).sort("turn_index", 1)
        return [Commitment.model_validate(_strip(d)) async for d in cursor]

    async def supersede(self, commitment_id: str, superseded_by: str) -> None:
        await self._c.update_one(
            {"_id": commitment_id},
            {"$set": {"superseded": True, "superseded_by": superseded_by}},
        )

    async def redact(self, commitment_id: str, reason: str) -> None:
        await self._c.update_one(
            {"_id": commitment_id},
            {"$set": {"redacted": True, "redaction_reason": reason}},
        )
