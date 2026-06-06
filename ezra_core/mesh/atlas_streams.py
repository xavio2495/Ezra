"""Atlas Stream Processing connector — live telemetry via MongoDB MCP's
``atlas-streams-*`` tools.

This is the partner-track piece (`docs/product-concept.md`): telemetry time-series
flow through **Atlas Stream Processing**, and Ezra reaches them via MongoDB MCP's
``atlas-streams-{build,discover,manage,teardown}`` tool surface. A stream
*processor* reads a source (Kafka / change stream), runs an aggregation pipeline,
and writes to a sink; "fetching live telemetry" samples that running processor.

The MCP tool surface is injected as a ``StreamToolInvoker`` (``call(tool, args)``)
so unit tests use a deterministic fake — exactly how :mod:`ezra_core.mesh.mongodb_mcp`
injects a collection instead of speaking the wire protocol. The real wiring
(:class:`McpHttpInvoker`) does a JSON-RPC ``tools/call`` against the MCP server's
Streamable-HTTP endpoint; it is lazy + live-only (not unit-covered).

Like all MongoDB sources, there is **no query-time time-travel**
(``time_travel_available=False``); ``as_of`` is ignored.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional, Protocol

from ezra_core.mesh.base import BaseConnector
from ezra_core.schemas.mesh import MeshResult


class StreamToolInvoker(Protocol):
    async def call(self, tool: str, arguments: dict) -> Any: ...


def _extract_docs(payload: Any) -> list[dict]:
    """Coerce an ``atlas-streams-*`` result into a list of row dicts.

    Defensive: handles a raw list, a dict wrapping the rows under a common key,
    and MCP ``content`` blocks whose ``text`` is JSON (or plain text)."""
    # Unwrap MCP content blocks ({"content": [{"type": "text", "text": "..."}]}).
    if isinstance(payload, dict) and isinstance(payload.get("content"), list):
        texts = [
            b["text"]
            for b in payload["content"]
            if isinstance(b, dict) and b.get("type") == "text" and b.get("text")
        ]
        joined = "\n".join(texts)
        if not joined:
            return []
        try:
            payload = json.loads(joined)
        except (json.JSONDecodeError, ValueError):
            return [{"text": joined}]

    if isinstance(payload, list):
        return [d for d in payload if isinstance(d, dict)]
    if isinstance(payload, dict):
        for key in ("documents", "data", "sample", "results", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                return [d for d in value if isinstance(d, dict)]
        return [payload]
    return []


class AtlasStreamsConnector(BaseConnector):
    """Read live telemetry from (and manage) one Atlas Stream Processing processor.

    ``fetch`` samples the running processor and returns the latest documents as a
    typed ``MeshResult``. The lifecycle methods (``deploy`` / ``start`` / ``stop``
    / ``diagnose`` / ``teardown``) are how the demo wires a processor for live
    telemetry ingestion before agents read from it.
    """

    time_travel_available = False

    def __init__(
        self,
        invoker: StreamToolInvoker,
        *,
        workspace: str,
        processor: str,
        source_name: Optional[str] = None,
        topics: Optional[list[str]] = None,
        limit: int = 50,
    ) -> None:
        self._invoker = invoker
        self._workspace = workspace
        self._processor = processor
        self._source = source_name or processor
        self._topics = topics or []
        self._limit = limit

    def _target(self, **extra: Any) -> dict:
        return {"workspace": self._workspace, "name": self._processor, **extra}

    async def fetch(
        self,
        query: str,
        agent_id: str,
        permission_scope: list[str],
        as_of: Optional[datetime] = None,
    ) -> MeshResult:
        payload = await self._invoker.call(
            "atlas-streams-discover", self._target(action="inspect-processor")
        )
        docs = _extract_docs(payload)[: self._limit]
        return MeshResult(
            data=docs,
            provenance=self._provenance(source=f"atlas-streams:{self._source}"),
            topics=self._topics,
        )

    # -- lifecycle (demo wiring: build → start → read; stop/teardown to clean up) #
    async def deploy(self, *, pipeline: list[dict], connection: str) -> Any:
        """Create the processor (``atlas-streams-build``) and start it."""
        await self._invoker.call(
            "atlas-streams-build",
            self._target(resource="processor", pipeline=pipeline, connection=connection),
        )
        return await self.start()

    async def start(self) -> Any:
        return await self._invoker.call(
            "atlas-streams-manage", self._target(action="start-processor")
        )

    async def stop(self) -> Any:
        return await self._invoker.call(
            "atlas-streams-manage", self._target(action="stop-processor")
        )

    async def diagnose(self) -> Any:
        """Processor health/stats (``atlas-streams-discover diagnose-processor``)."""
        return await self._invoker.call(
            "atlas-streams-discover", self._target(action="diagnose-processor")
        )

    async def teardown(self) -> Any:
        return await self._invoker.call(
            "atlas-streams-teardown", self._target(resource="processor")
        )


class McpHttpInvoker:
    """Minimal MongoDB-MCP Streamable-HTTP client: one JSON-RPC ``tools/call``.

    Real wiring for :class:`AtlasStreamsConnector`. Lazy (imports httpx on call)
    and **live-only** — unit tests inject a fake invoker instead. Best-effort: a
    transport/JSON-RPC error raises so the caller (router fetch) can treat it like
    any other connector failure.
    """

    def __init__(
        self, url: str, *, headers: Optional[dict] = None, timeout: float = 30.0
    ) -> None:
        self._url = url
        self._headers = headers or {}
        self._timeout = timeout

    async def call(self, tool: str, arguments: dict) -> Any:
        import httpx

        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
        headers = {"Accept": "application/json, text/event-stream", **self._headers}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(self._url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        if "error" in data:
            raise RuntimeError(f"MCP tool {tool} failed: {data['error']}")
        return data.get("result", data)


def atlas_streams_connector_from_settings(
    settings,
    *,
    workspace: Optional[str] = None,
    processor: Optional[str] = None,
    topics: Optional[list[str]] = None,
    limit: int = 50,
    invoker: Optional[StreamToolInvoker] = None,
) -> AtlasStreamsConnector:
    """Build the connector against the configured MCP endpoint
    (``EZRA_MONGODB_MCP_URL``) for the configured workspace/processor."""
    return AtlasStreamsConnector(
        invoker or McpHttpInvoker(settings.mongodb_mcp_url),
        workspace=workspace or settings.atlas_streams_workspace,
        processor=processor or settings.atlas_streams_processor,
        topics=topics,
        limit=limit,
    )
