"""Semantic memory — core/archival split with cross-graph (inheritance) loads.

Core facts are auto-loaded at agent spawn (this graph + inherited graphs),
scope-filtered. Archival facts live outside the always-needed set: they are
recalled per-turn by **vector similarity** to the current input, scope-filtered
(``recall_archival``) — in-memory cosine for tests, Atlas ``$vectorSearch`` in
production — and still fetched in bulk by topic/scope (``get_archival``).
Cross-graph loading is by ``source_graph_ids``, matched against each fact's
``source_session_graph_ids``.

The embedder is injected (the same structural ``Embedder`` as the belief checker
/ warm tier). When present, ``add`` embeds the fact's "subject predicate object"
text so it is searchable; without one the store degrades to topic/scope only
(``recall_archival`` returns nothing).
"""

from __future__ import annotations

from typing import Optional, Protocol

from pymongo import AsyncMongoClient, ReturnDocument

from ezra_core.belief.checker import Embedder, cosine_similarity
from ezra_core.schemas.memory import SemanticFact
from ezra_core.scope import filter_by_scope


def _from_any_graph(fact: SemanticFact, source_graph_ids: list[str]) -> bool:
    return bool(set(fact.source_session_graph_ids) & set(source_graph_ids))


def _fact_text(fact: SemanticFact) -> str:
    return f"{fact.subject} {fact.predicate} {fact.object}"


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
    async def recall_archival(
        self,
        query: str,
        *,
        user_id: str,
        scope_topics: set[str],
        limit: int = 5,
        source_graph_ids: Optional[list[str]] = None,
    ) -> list[SemanticFact]: ...
    async def increment_access(self, fact_id: str) -> int: ...


class InMemorySemanticStore:
    def __init__(self, embedder: Optional[Embedder] = None) -> None:
        self._items: dict[str, SemanticFact] = {}
        self._embedder = embedder

    async def add(self, fact: SemanticFact) -> None:
        fact = fact.model_copy(deep=True)
        if self._embedder is not None and fact.embedding is None:
            fact.embedding = list(self._embedder.encode(_fact_text(fact)))
        self._items[fact.id] = fact

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

    async def recall_archival(
        self,
        query: str,
        *,
        user_id: str,
        scope_topics: set[str],
        limit: int = 5,
        source_graph_ids: Optional[list[str]] = None,
    ) -> list[SemanticFact]:
        if self._embedder is None:
            return []
        q = list(self._embedder.encode(query))
        candidates = self._select(
            tier="archival",
            user_id=user_id,
            scope_topics=scope_topics,
            source_graph_ids=source_graph_ids,
        )
        scored = [
            (cosine_similarity(q, f.embedding), f)
            for f in candidates
            if f.embedding is not None
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [f for _, f in scored[:limit]]

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
        *,
        embedder: Optional[Embedder] = None,
        vector_index: str = "semantic_archival_vector",
    ) -> None:
        self._c = client[db_name][collection]
        self._embedder = embedder
        self._vector_index = vector_index

    async def add(self, fact: SemanticFact) -> None:
        if self._embedder is not None and fact.embedding is None:
            fact = fact.model_copy(update={"embedding": list(self._embedder.encode(_fact_text(fact)))})
        doc = fact.model_dump(mode="json")
        doc["_id"] = fact.id
        await self._c.replace_one({"_id": fact.id}, doc, upsert=True)

    async def ensure_vector_index(self, num_dimensions: int) -> None:
        """Create the Atlas Vector Search index over ``embedding`` if absent.

        Best-effort and Atlas-only (a non-Atlas Mongo has no search indexes).
        ``user_id`` / ``tier`` / ``source_session_graph_ids`` are declared as
        ``filter`` fields so ``recall_archival`` can pre-filter inside
        ``$vectorSearch``. Index build is eventually-consistent — call this at
        wiring/ingest time, not on the recall hot path."""
        from pymongo.operations import SearchIndexModel

        existing = {ix["name"] async for ix in await self._c.list_search_indexes()}
        if self._vector_index in existing:
            return
        await self._c.create_search_index(
            SearchIndexModel(
                definition={
                    "fields": [
                        {
                            "type": "vector",
                            "path": "embedding",
                            "numDimensions": num_dimensions,
                            "similarity": "cosine",
                        },
                        {"type": "filter", "path": "user_id"},
                        {"type": "filter", "path": "tier"},
                        {"type": "filter", "path": "source_session_graph_ids"},
                    ]
                },
                name=self._vector_index,
                type="vectorSearch",
            )
        )

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

    async def recall_archival(
        self,
        query: str,
        *,
        user_id: str,
        scope_topics: set[str],
        limit: int = 5,
        source_graph_ids: Optional[list[str]] = None,
    ) -> list[SemanticFact]:
        if self._embedder is None:
            return []
        q = list(self._embedder.encode(query))
        vfilter: dict = {"user_id": user_id, "tier": "archival"}
        if source_graph_ids is not None:
            vfilter["source_session_graph_ids"] = {"$in": source_graph_ids}
        pipeline = [
            {
                "$vectorSearch": {
                    "index": self._vector_index,
                    "path": "embedding",
                    "queryVector": q,
                    "numCandidates": max(limit * 20, 100),
                    "limit": limit * 4,
                    "filter": vfilter,
                }
            }
        ]
        cursor = await self._c.aggregate(pipeline)
        facts = [
            SemanticFact.model_validate(_strip(d))
            async for d in cursor
            if d.get("superseded_by") is None
        ]
        return filter_by_scope(facts, scope_topics)[:limit]

    async def increment_access(self, fact_id: str) -> int:
        doc = await self._c.find_one_and_update(
            {"_id": fact_id},
            {"$inc": {"access_count": 1}},
            return_document=ReturnDocument.AFTER,
        )
        return doc["access_count"] if doc is not None else 0
