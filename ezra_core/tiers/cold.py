"""Cold tier — MongoDB Atlas. Wires one async client (Stable API v1, matching
the Atlas connection snippet) and exposes the four cold-tier stores that sit on
top of it: beliefs, semantic, episodic, procedural.

Unit tests construct the individual stores with in-memory backends; this module
is the production wiring against a real cluster.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pymongo import AsyncMongoClient
from pymongo.server_api import ServerApi

from ezra_core.belief.checker import Embedder
from ezra_core.belief.store import MongoBeliefStore
from ezra_core.config import EzraSettings
from ezra_core.memory.episodic import MongoEpisodicStore
from ezra_core.memory.procedural import MongoProceduralStore
from ezra_core.memory.semantic import MongoSemanticStore


def cold_client(uri: str) -> AsyncMongoClient:
    """Atlas client with Stable API v1 (the documented connection pattern)."""
    return AsyncMongoClient(uri, server_api=ServerApi("1"))


@dataclass
class ColdTier:
    """Bundle of the four cold-tier stores sharing one Atlas client."""

    client: AsyncMongoClient
    beliefs: MongoBeliefStore
    semantic: MongoSemanticStore
    episodic: MongoEpisodicStore
    procedural: MongoProceduralStore

    async def close(self) -> None:
        await self.client.close()


def cold_tier_from_settings(
    settings: EzraSettings, *, embedder: Optional[Embedder] = None
) -> ColdTier:
    if not settings.mongodb_uri:
        raise ValueError("EZRA_MONGODB_URI is not set")
    client = cold_client(settings.mongodb_uri)
    db = settings.mongodb_db
    return ColdTier(
        client=client,
        beliefs=MongoBeliefStore(client, db),
        semantic=MongoSemanticStore(
            client, db, embedder=embedder, vector_index=settings.semantic_vector_index
        ),
        episodic=MongoEpisodicStore(client, db),
        procedural=MongoProceduralStore(client, db),
    )
