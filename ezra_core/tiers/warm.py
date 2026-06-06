"""Warm tier — Qdrant. Compressed prior turns / topic summaries, recalled by
semantic similarity and filtered by session graph + permission scope + TTL.

The embedder is injected (same structural ``Embedder`` as the belief checker)
so unit tests use a deterministic fake and an in-memory Qdrant
(``AsyncQdrantClient(location=":memory:")``) — no server, no network. In
production the embedder is Gemini ``text-embedding-004`` and the client points
at the Qdrant container/GKE service.

Scope semantics match the cold tier: an untopiced summary is visible to any
scope; otherwise its topics must intersect the scope. Qdrant filters by
``session_graph_id`` server-side; the topic/TTL rules are applied in Python
(we over-fetch, then filter) because "untopiced OR intersecting" isn't a single
Qdrant clause.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from qdrant_client import AsyncQdrantClient, models

from ezra_core.belief.checker import Embedder
from ezra_core.schemas.memory import WarmSummary
from ezra_core.scope import matches_scope


class WarmTier:
    def __init__(
        self,
        client: AsyncQdrantClient,
        embedder: Embedder,
        *,
        collection: str = "warm_summaries",
        ttl_hours: int = 24,
    ) -> None:
        self._client = client
        self._embedder = embedder
        self._collection = collection
        self._ttl_hours = ttl_hours

    async def _ensure_collection(self, vector_size: int) -> None:
        if not await self._client.collection_exists(self._collection):
            await self._client.create_collection(
                self._collection,
                vectors_config=models.VectorParams(
                    size=vector_size, distance=models.Distance.COSINE
                ),
            )

    async def add(self, summary: WarmSummary) -> None:
        vector = list(self._embedder.encode(summary.summary))
        await self._ensure_collection(len(vector))
        await self._client.upsert(
            self._collection,
            points=[
                models.PointStruct(
                    id=summary.id,
                    vector=vector,
                    payload=summary.model_dump(mode="json"),
                )
            ],
        )

    async def recall(
        self,
        *,
        session_graph_id: str,
        query: str,
        scope_topics: set[str],
        limit: int = 5,
        now: Optional[datetime] = None,
    ) -> list[WarmSummary]:
        if not await self._client.collection_exists(self._collection):
            return []

        vector = list(self._embedder.encode(query))
        # Over-fetch, since topic/TTL filtering happens after the vector search.
        response = await self._client.query_points(
            self._collection,
            query=vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="session_graph_id",
                        match=models.MatchValue(value=session_graph_id),
                    )
                ]
            ),
            limit=limit * 4,
            with_payload=True,
        )

        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=self._ttl_hours)
        out: list[WarmSummary] = []
        for point in response.points:
            summary = WarmSummary.model_validate(point.payload)
            if summary.created_at < cutoff:
                continue
            if not matches_scope(summary.topics, scope_topics):
                continue
            out.append(summary)
            if len(out) >= limit:
                break
        return out

    async def evict_expired(self, *, now: Optional[datetime] = None) -> None:
        """Compaction hook — drop summaries past TTL. (Promotion to cold is the
        learning meta-agent's job.)"""
        if not await self._client.collection_exists(self._collection):
            return
        now = now or datetime.now(timezone.utc)
        cutoff = (now - timedelta(hours=self._ttl_hours)).isoformat()
        await self._client.delete(
            self._collection,
            points_selector=models.Filter(
                must=[
                    models.FieldCondition(
                        key="created_at", range=models.DatetimeRange(lt=cutoff)
                    )
                ]
            ),
        )
