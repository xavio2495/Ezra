"""Semantic memory — core/archival split with cross-graph (inheritance) loads.

Core facts are auto-loaded at agent spawn (this graph + inherited graphs),
scope-filtered. Archival facts live outside the always-needed set; in this
session they are fetched by topic/scope (vector similarity recall arrives with
the warm tier in Session 4). Cross-graph loading is by ``source_graph_ids``,
matched against each fact's ``source_session_graph_ids``.
"""

from __future__ import annotations

from typing import Optional, Protocol

from pymongo import AsyncMongoClient, ReturnDocument

from ezra_core.schemas.memory import SemanticFact
from ezra_core.scope import filter_by_scope


def _from_any_graph(fact: SemanticFact, source_graph_ids: list[str]) -> bool:
    return bool(set(fact.source_session_graph_ids) & set(source_graph_ids))


class SemanticStore(Protocol):
    async def add(self, fact: SemanticFact) -> None: ...
    async def get(self, fact_id: str) -> Optional[SemanticFact]: ...
    async def get_core(
        self, *, user_id: str, scope_topics: set[str], source_graph_ids: list[str]
    ) -> list[SemanticFact]: ...
    async def get_archival(
        self,
        *,
        user_id: str,
        scope_topics: set[str],
        source_graph_ids: Optional[list[str]] = None,
    ) -> list[SemanticFact]: ...
    async def increment_access(self, fact_id: str) -> int: ...


class InMemorySemanticStore:
    def __init__(self) -> None:
        self._items: dict[str, SemanticFact] = {}

    async def add(self, fact: SemanticFact) -> None:
        self._items[fact.id] = fact.model_copy(deep=True)

    async def get(self, fact_id: str) -> Optional[SemanticFact]:
        f = self._items.get(fact_id)
        return f.model_copy(deep=True) if f is not None else None

    def _select(
        self,
        *,
        tier: str,
        user_id: str,
        scope_topics: set[str],
        source_graph_ids: Optional[list[str]],
    ) -> list[SemanticFact]:
        facts = [
            f.model_copy(deep=True)
            for f in self._items.values()
            if f.tier == tier
            and f.user_id == user_id
            and f.superseded_by is None
            and (source_graph_ids is None or _from_any_graph(f, source_graph_ids))
        ]
        return filter_by_scope(facts, scope_topics)

    async def get_core(
        self, *, user_id: str, scope_topics: set[str], source_graph_ids: list[str]
    ) -> list[SemanticFact]:
        return self._select(
            tier="core",
            user_id=user_id,
            scope_topics=scope_topics,
            source_graph_ids=source_graph_ids,
        )

    async def get_archival(
        self,
        *,
        user_id: str,
        scope_topics: set[str],
        source_graph_ids: Optional[list[str]] = None,
    ) -> list[SemanticFact]:
        return self._select(
            tier="archival",
            user_id=user_id,
            scope_topics=scope_topics,
            source_graph_ids=source_graph_ids,
        )

    async def increment_access(self, fact_id: str) -> int:
        f = self._items.get(fact_id)
        if f is None:
            return 0
        f.access_count += 1
        return f.access_count


def _strip(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


class MongoSemanticStore:
    def __init__(
        self,
        client: AsyncMongoClient,
        db_name: str,
        collection: str = "semantic_facts",
    ) -> None:
        self._c = client[db_name][collection]

    async def add(self, fact: SemanticFact) -> None:
        doc = fact.model_dump(mode="json")
        doc["_id"] = fact.id
        await self._c.replace_one({"_id": fact.id}, doc, upsert=True)

    async def get(self, fact_id: str) -> Optional[SemanticFact]:
        doc = await self._c.find_one({"_id": fact_id})
        return SemanticFact.model_validate(_strip(doc)) if doc is not None else None

    async def _select(
        self,
        *,
        tier: str,
        user_id: str,
        scope_topics: set[str],
        source_graph_ids: Optional[list[str]],
    ) -> list[SemanticFact]:
        query: dict = {"tier": tier, "user_id": user_id, "superseded_by": None}
        if source_graph_ids is not None:
            query["source_session_graph_ids"] = {"$in": source_graph_ids}
        cursor = self._c.find(query)
        facts = [SemanticFact.model_validate(_strip(d)) async for d in cursor]
        return filter_by_scope(facts, scope_topics)

    async def get_core(
        self, *, user_id: str, scope_topics: set[str], source_graph_ids: list[str]
    ) -> list[SemanticFact]:
        return await self._select(
            tier="core",
            user_id=user_id,
            scope_topics=scope_topics,
            source_graph_ids=source_graph_ids,
        )

    async def get_archival(
        self,
        *,
        user_id: str,
        scope_topics: set[str],
        source_graph_ids: Optional[list[str]] = None,
    ) -> list[SemanticFact]:
        return await self._select(
            tier="archival",
            user_id=user_id,
            scope_topics=scope_topics,
            source_graph_ids=source_graph_ids,
        )

    async def increment_access(self, fact_id: str) -> int:
        doc = await self._c.find_one_and_update(
            {"_id": fact_id},
            {"$inc": {"access_count": 1}},
            return_document=ReturnDocument.AFTER,
        )
        return doc["access_count"] if doc is not None else 0
