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
        project_id: Optional[str] = None,
        source_name: Optional[str] = None,
        topics: Optional[list[str]] = None,
        limit: int = 50,
    ) -> None:
        self._invoker = invoker
        self._workspace = workspace
        self._processor = processor
        # The atlas-streams-* MCP tools are project-scoped — every call needs the
        # Atlas project (group) id, confirmed live (the server rejects calls without
        # it). None omits it (e.g. when a fake invoker doesn't need it).
        self._project_id = project_id
        self._source = source_name or processor
        self._topics = topics or []
        self._limit = limit

    def _target(self, **extra: Any) -> dict:
        target = {"workspace": self._workspace, "name": self._processor, **extra}
        if self._project_id:
            target["projectId"] = self._project_id
        return target

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

    async def list_workspaces(self) -> Any:
        """Project-scoped discovery (``atlas-streams-discover list-workspaces``) —
        read-only, needs no workspace/processor (but is project-scoped). Useful to
        confirm connectivity to the MCP server before a processor exists."""
        args: dict = {"action": "list-workspaces"}
        if self._project_id:
            args["projectId"] = self._project_id
        return await self._invoker.call("atlas-streams-discover", args)


_DEFAULT_PROTOCOL_VERSION = "2025-06-18"


def _parse_jsonrpc(content_type: str, text: str) -> dict:
    """Parse an MCP Streamable-HTTP response body. The server may reply with a
    plain JSON object or a Server-Sent-Events stream (`event: message` / `data:
    {jsonrpc...}`); for SSE we concatenate the ``data:`` payloads and JSON-decode.
    """
    if "text/event-stream" in (content_type or ""):
        data_lines = [
            line[len("data:") :].strip()
            for line in text.splitlines()
            if line.strip().startswith("data:")
        ]
        text = "".join(data_lines)
    text = text.strip()
    return json.loads(text) if text else {}


class McpHttpInvoker:
    """MongoDB-MCP Streamable-HTTP client (real wiring for
    :class:`AtlasStreamsConnector`).

    Speaks the MCP Streamable-HTTP lifecycle: on the first call it performs the
    ``initialize`` handshake (capturing the server's ``Mcp-Session-Id`` and the
    negotiated protocol version), sends the ``notifications/initialized`` ack, then
    issues ``tools/call`` with the session header. A spec-compliant server rejects
    a bare ``tools/call`` without this, so the handshake is mandatory. Responses
    come back as JSON *or* SSE — both are handled.

    Lazy (imports httpx on first call) and best-effort: a transport / JSON-RPC
    error raises so the caller (router fetch) treats it like any connector failure.
    Unit tests inject a fake invoker; this class is exercised live + via an httpx
    ``MockTransport`` test.
    """

    def __init__(
        self,
        url: str,
        *,
        headers: Optional[dict] = None,
        timeout: float = 30.0,
        protocol_version: str = _DEFAULT_PROTOCOL_VERSION,
    ) -> None:
        self._url = url
        self._headers = headers or {}
        self._timeout = timeout
        self._protocol_version = protocol_version
        self._session_id: Optional[str] = None
        self._initialized = False
        self._rpc_id = 0

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    async def _post(self, client, payload: dict, *, with_protocol_header: bool, expect_body: bool):
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            **self._headers,
        }
        if with_protocol_header:
            headers["MCP-Protocol-Version"] = self._protocol_version
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        resp = await client.post(self._url, json=payload, headers=headers)
        # The server assigns the session on the initialize response (header).
        sid = resp.headers.get("mcp-session-id")
        if sid:
            self._session_id = sid
        resp.raise_for_status()
        if not expect_body:
            return None
        data = _parse_jsonrpc(resp.headers.get("content-type", ""), resp.text)
        if isinstance(data, dict) and data.get("error"):
            raise RuntimeError(f"MCP error: {data['error']}")
        return data

    async def _ensure_session(self, client) -> None:
        if self._initialized:
            return
        init = await self._post(
            client,
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": self._protocol_version,
                    "capabilities": {},
                    "clientInfo": {"name": "ezra-atlas-streams", "version": "0.1"},
                },
            },
            with_protocol_header=False,  # negotiated on the response, not sent here
            expect_body=True,
        )
        negotiated = (init or {}).get("result", {}).get("protocolVersion")
        if negotiated:
            self._protocol_version = negotiated
        # Ack — a notification (no id); server returns 202 with no body.
        await self._post(
            client,
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            with_protocol_header=True,
            expect_body=False,
        )
        self._initialized = True

    async def call(self, tool: str, arguments: dict) -> Any:
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            await self._ensure_session(client)
            data = await self._post(
                client,
                {
                    "jsonrpc": "2.0",
                    "id": self._next_id(),
                    "method": "tools/call",
                    "params": {"name": tool, "arguments": arguments},
                },
                with_protocol_header=True,
                expect_body=True,
            )
        if isinstance(data, dict) and "result" in data:
            return data["result"]
        return data


def atlas_streams_connector_from_settings(
    settings,
    *,
    workspace: Optional[str] = None,
    processor: Optional[str] = None,
    project_id: Optional[str] = None,
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
        project_id=project_id or (settings.mongodb_atlas_project_id or None),
        topics=topics,
        limit=limit,
    )
