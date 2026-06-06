"""EzraMemoryService — Ezra registered as a first-class Google ADK memory service.

``Runner(memory_service=EzraMemoryService(ezra, ...))`` makes Ezra the backing
store for ADK's native memory plumbing: ``add_session_to_memory`` ingests a
session's turns into Ezra's warm tier, and ``search_memory`` answers ADK
``load_memory`` / ``search_memory`` calls from Ezra's warm recall + semantic
archival. This is the formal "Ezra is an ADK Service" integration, distinct from
the Ezra toolset (which exposes belief/commit/rewind/revert as agent tools).

``google.adk`` / ``google.genai`` are imported lazily so importing this module
never requires the optional ``agents`` dependency.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, Optional
from uuid import uuid4

from ezra_core.schemas.memory import WarmSummary

if TYPE_CHECKING:
    from ezra_core.runtime import Ezra


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _event_text(event) -> str:
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None) or []
    return " ".join(p.text for p in parts if getattr(p, "text", None)).strip()


class EzraMemoryService:
    """ADK ``BaseMemoryService`` backed by an Ezra runtime.

    Built lazily as a ``BaseMemoryService`` subclass so the module imports without
    google-adk. ``app_name_to_graph`` maps an ADK app_name to an Ezra
    ``session_graph_id`` (default: a single configured graph); ``scope_topics``
    bounds recall to a permission scope (default: unrestricted).
    """

    def __new__(cls, *args, **kwargs):
        from google.adk.memory.base_memory_service import BaseMemoryService

        if not issubclass(cls, BaseMemoryService):
            cls = type("EzraMemoryService", (EzraMemoryService, BaseMemoryService), {})
        return object.__new__(cls)

    def __init__(
        self,
        ezra: Ezra,
        *,
        session_graph_id: str = "adk-memory",
        scope_topics: Optional[set[str]] = None,
        app_name_to_graph: Optional[Callable[[str], str]] = None,
        recall_limit: int = 5,
    ) -> None:
        self._ezra = ezra
        self._graph_id = session_graph_id
        self._scope = scope_topics  # None = unrestricted
        self._resolve = app_name_to_graph or (lambda app_name: self._graph_id)
        self._limit = recall_limit

    # -- ingest ----------------------------------------------------------- #
    async def add_session_to_memory(self, session) -> None:
        """Write each text-bearing event of an ADK session into Ezra's warm tier
        as a recallable summary, attributed to the event's author."""
        if self._ezra.warm is None:
            return
        graph_id = self._resolve(getattr(session, "app_name", ""))
        for event in getattr(session, "events", []) or []:
            text = _event_text(event)
            if not text:
                continue
            await self._ezra.warm.add(
                WarmSummary(
                    id=str(uuid4()),
                    session_graph_id=graph_id,
                    agent_id=getattr(event, "author", None),
                    summary=text,
                    topics=[],
                    created_at=_utcnow(),
                )
            )

    # -- recall ----------------------------------------------------------- #
    async def search_memory(self, *, app_name: str, user_id: str, query: str):
        """Answer an ADK memory search from Ezra's warm recall + semantic archival,
        returning the matches as ADK ``MemoryEntry`` objects."""
        from google.adk.memory.base_memory_service import SearchMemoryResponse
        from google.adk.memory.memory_entry import MemoryEntry
        from google.genai import types

        graph_id = self._resolve(app_name)
        memories = []

        if self._ezra.warm is not None:
            summaries = await self._ezra.warm.recall(
                session_graph_id=graph_id,
                query=query,
                scope_topics=self._scope if self._scope is not None else set(),
                limit=self._limit,
            )
            for s in summaries:
                memories.append(
                    MemoryEntry(
                        content=types.Content(
                            role="model", parts=[types.Part(text=s.summary)]
                        ),
                        author=s.agent_id,
                        timestamp=s.created_at.isoformat(),
                    )
                )

        facts = await self._ezra.semantic_store.get_archival(
            user_id=user_id,
            scope_topics=self._scope if self._scope is not None else set(),
            source_graph_ids=[graph_id],
        )
        for f in facts:
            memories.append(
                MemoryEntry(
                    content=types.Content(
                        role="model",
                        parts=[types.Part(text=f"{f.subject} {f.predicate} {f.object}")],
                    ),
                    timestamp=f.updated_at.isoformat(),
                )
            )

        return SearchMemoryResponse(memories=memories)
