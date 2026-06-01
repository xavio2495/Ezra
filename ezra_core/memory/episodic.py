"""Episodic memory — what happened, when, in sequence. Hydrated by session
graph + optional timestamp window, scope-filtered."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol

from pymongo import AsyncMongoClient

from ezra_core.schemas.memory import EpisodicMemory
from ezra_core.scope import filter_by_scope


class EpisodicStore(Protocol):
    async def add(self, memory: EpisodicMemory) -> None: ...
    async def get_for_graph(
        self,
        session_graph_id: str,
        *,
        scope_topics: Optional[set[str]] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> list[EpisodicMemory]: ...


class InMemoryEpisodicStore:
    def __init__(self) -> None:
        self._items: list[EpisodicMemory] = []

    async def add(self, memory: EpisodicMemory) -> None:
        self._items.append(memory.model_copy(deep=True))

    async def get_for_graph(
        self,
        session_graph_id: str,
        *,
        scope_topics: Optional[set[str]] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> list[EpisodicMemory]:
        out = [
            m.model_copy(deep=True)
            for m in self._items
            if m.session_graph_id == session_graph_id
            and (since is None or m.timestamp >= since)
            and (until is None or m.timestamp <= until)
        ]
        out.sort(key=lambda m: m.timestamp)
        if scope_topics is not None:
            out = filter_by_scope(out, scope_topics)
        return out


def _strip(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


class MongoEpisodicStore:
    def __init__(
        self,
        client: AsyncMongoClient,
        db_name: str,
        collection: str = "episodic_memory",
    ) -> None:
        self._c = client[db_name][collection]

    async def add(self, memory: EpisodicMemory) -> None:
        doc = memory.model_dump(mode="json")
        doc["_id"] = memory.id
        await self._c.replace_one({"_id": memory.id}, doc, upsert=True)

    async def get_for_graph(
        self,
        session_graph_id: str,
        *,
        scope_topics: Optional[set[str]] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> list[EpisodicMemory]:
        query: dict = {"session_graph_id": session_graph_id}
        ts: dict = {}
        if since is not None:
            ts["$gte"] = since.isoformat()
        if until is not None:
            ts["$lte"] = until.isoformat()
        if ts:
            query["timestamp"] = ts
        cursor = self._c.find(query).sort("timestamp", 1)
        out = [EpisodicMemory.model_validate(_strip(d)) async for d in cursor]
        if scope_topics is not None:
            out = filter_by_scope(out, scope_topics)
        return out
