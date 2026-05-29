"""Session graph runtime: persistence stores + the manager users interact with.

Public API (matches README/HANDOFF)::

    graph = await SessionGraph.create(store=store, session_graph_id="...", ...)
    reg   = await graph.spawn_agent(agent_id="...", permission_scope=[...])
    await graph.terminate_agent("...")

The persisted Pydantic model lives in ``ezra_core.schemas.session_graph`` and is
imported here as ``SessionGraphRecord`` to avoid clashing with this manager.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Protocol

from pymongo import AsyncMongoClient

from ezra_core.config import EzraSettings
from ezra_core.schemas.session_graph import (
    AgentRegistration,
    MergeStrategy,
    SessionGraphState,
)
from ezra_core.schemas.session_graph import SessionGraph as SessionGraphRecord


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #
class SessionGraphStore(Protocol):
    """Persistence port for session-graph state."""

    async def save(self, record: SessionGraphRecord) -> None: ...
    async def get(self, session_graph_id: str) -> Optional[SessionGraphRecord]: ...
    async def delete(self, session_graph_id: str) -> None: ...


class InMemorySessionGraphStore:
    """In-memory store for unit tests. Stores deep copies to avoid aliasing."""

    def __init__(self) -> None:
        self._records: dict[str, SessionGraphRecord] = {}

    async def save(self, record: SessionGraphRecord) -> None:
        self._records[record.session_graph_id] = record.model_copy(deep=True)

    async def get(self, session_graph_id: str) -> Optional[SessionGraphRecord]:
        record = self._records.get(session_graph_id)
        return record.model_copy(deep=True) if record is not None else None

    async def delete(self, session_graph_id: str) -> None:
        self._records.pop(session_graph_id, None)


class MongoSessionGraphStore:
    """MongoDB Atlas-backed store (the real persistence). Uses PyMongo's async API."""

    def __init__(
        self,
        client: AsyncMongoClient,
        db_name: str,
        collection: str = "session_graphs",
    ) -> None:
        self._collection = client[db_name][collection]

    async def save(self, record: SessionGraphRecord) -> None:
        doc = record.model_dump(mode="json")
        doc["_id"] = record.session_graph_id
        await self._collection.replace_one({"_id": record.session_graph_id}, doc, upsert=True)

    async def get(self, session_graph_id: str) -> Optional[SessionGraphRecord]:
        doc = await self._collection.find_one({"_id": session_graph_id})
        if doc is None:
            return None
        doc.pop("_id", None)
        return SessionGraphRecord.model_validate(doc)

    async def delete(self, session_graph_id: str) -> None:
        await self._collection.delete_one({"_id": session_graph_id})


def mongo_store_from_settings(settings: EzraSettings) -> MongoSessionGraphStore:
    if not settings.mongodb_uri:
        raise ValueError("EZRA_MONGODB_URI is not set")
    client = AsyncMongoClient(settings.mongodb_uri)
    return MongoSessionGraphStore(client, settings.mongodb_db)


# --------------------------------------------------------------------------- #
# Manager
# --------------------------------------------------------------------------- #
class SessionGraph:
    """Runtime handle for one session graph: spawns/terminates agents and persists."""

    def __init__(
        self,
        record: SessionGraphRecord,
        store: SessionGraphStore,
        custom_resolver=None,
    ) -> None:
        self._record = record
        self._store = store
        # Held in-process only; never serialised (per HANDOFF).
        self._custom_resolver = custom_resolver

    # -- read-only views -------------------------------------------------- #
    @property
    def record(self) -> SessionGraphRecord:
        return self._record

    @property
    def session_graph_id(self) -> str:
        return self._record.session_graph_id

    @property
    def state(self) -> SessionGraphState:
        return self._record.state

    @property
    def active_agents(self) -> list[AgentRegistration]:
        return list(self._record.active_agents)

    @property
    def terminated_agents(self) -> list[AgentRegistration]:
        return list(self._record.terminated_agents)

    # -- lifecycle -------------------------------------------------------- #
    @classmethod
    async def create(
        cls,
        *,
        store: SessionGraphStore,
        session_graph_id: str,
        description: str = "",
        merge_strategy: MergeStrategy = "last_write_wins",
        custom_resolver=None,
        inherits_from: Optional[list[str]] = None,
        manual_resolution_timeout_seconds: int = 30,
        inherit_episodic: bool = False,
        inherit_procedural: bool = True,
        archival_threshold_days: int = 90,
        belief_retention_days: Optional[int] = None,
    ) -> "SessionGraph":
        if merge_strategy == "custom" and custom_resolver is None:
            raise ValueError("merge_strategy='custom' requires a custom_resolver")

        record = SessionGraphRecord(
            session_graph_id=session_graph_id,
            created_at=_utcnow(),
            description=description,
            merge_strategy=merge_strategy,
            manual_resolution_timeout_seconds=manual_resolution_timeout_seconds,
            inherits_from=inherits_from or [],
            inherit_episodic=inherit_episodic,
            inherit_procedural=inherit_procedural,
            archival_threshold_days=archival_threshold_days,
            belief_retention_days=belief_retention_days,
        )
        graph = cls(record, store, custom_resolver)
        await store.save(record)
        return graph

    @classmethod
    async def load(
        cls,
        session_graph_id: str,
        store: SessionGraphStore,
        custom_resolver=None,
    ) -> "SessionGraph":
        record = await store.get(session_graph_id)
        if record is None:
            raise KeyError(f"session graph not found: {session_graph_id}")
        return cls(record, store, custom_resolver)

    # -- dynamic agent membership ---------------------------------------- #
    async def spawn_agent(
        self,
        *,
        agent_id: str,
        permission_scope: list[str],
        role: str = "",
    ) -> AgentRegistration:
        if self._record.state != SessionGraphState.ACTIVE:
            raise ValueError(f"cannot spawn into a {self._record.state.value} session graph")
        if any(a.agent_id == agent_id for a in self._record.active_agents):
            raise ValueError(f"agent already active: {agent_id}")

        registration = AgentRegistration(
            agent_id=agent_id,
            session_graph_id=self._record.session_graph_id,
            role=role,
            permission_scope=list(permission_scope),
            spawned_at=_utcnow(),
        )
        self._record.active_agents.append(registration)
        await self._store.save(self._record)
        return registration

    async def terminate_agent(self, agent_id: str) -> AgentRegistration:
        for i, agent in enumerate(self._record.active_agents):
            if agent.agent_id == agent_id:
                agent.terminated_at = _utcnow()
                self._record.active_agents.pop(i)
                self._record.terminated_agents.append(agent)
                await self._store.save(self._record)
                return agent
        raise KeyError(f"no active agent: {agent_id}")
