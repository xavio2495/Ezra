import json

import httpx
import pytest

from ezra_core.mesh.atlas_streams import (
    AtlasStreamsConnector,
    McpHttpInvoker,
    _extract_docs,
    _parse_jsonrpc,
    atlas_streams_connector_from_settings,
)
from ezra_core.config import EzraSettings


class FakeInvoker:
    """Records (tool, arguments) calls and returns a canned payload per tool."""

    def __init__(self, returns=None):
        self.calls = []
        self._returns = returns or {}

    async def call(self, tool, arguments):
        self.calls.append((tool, arguments))
        return self._returns.get(tool, {})


def _connector(invoker, **kw):
    return AtlasStreamsConnector(
        invoker, workspace="ws", processor="telemetry-proc", topics=["telemetry"], **kw
    )


async def test_fetch_samples_processor_and_returns_typed_result():
    sample = [{"speed": 312, "lap": 12}, {"speed": 305, "lap": 13}]
    invoker = FakeInvoker({"atlas-streams-discover": {"documents": sample}})
    conn = _connector(invoker)

    result = await conn.fetch("current telemetry?", "telemetry_analyst", ["telemetry"])

    tool, args = invoker.calls[0]
    assert tool == "atlas-streams-discover"
    assert args == {"workspace": "ws", "name": "telemetry-proc", "action": "inspect-processor"}
    assert result.data == sample
    assert result.provenance.source == "atlas-streams:telemetry-proc"
    assert result.provenance.time_travel_available is False
    assert result.topics == ["telemetry"]


async def test_fetch_respects_limit():
    rows = [{"i": i} for i in range(10)]
    invoker = FakeInvoker({"atlas-streams-discover": rows})
    conn = _connector(invoker, limit=3)
    result = await conn.fetch("q", "a", ["telemetry"])
    assert result.data == rows[:3]


async def test_fetch_parses_mcp_content_block():
    sample = [{"flag": "yellow", "sector": 2}]
    payload = {"content": [{"type": "text", "text": json.dumps(sample)}]}
    invoker = FakeInvoker({"atlas-streams-discover": payload})
    result = await _connector(invoker).fetch("q", "a", ["telemetry"])
    assert result.data == sample


async def test_deploy_builds_then_starts():
    invoker = FakeInvoker()
    conn = _connector(invoker)
    pipeline = [{"$match": {"speed": {"$gt": 300}}}]
    await conn.deploy(pipeline=pipeline, connection="kafka-src")

    tools = [c[0] for c in invoker.calls]
    assert tools == ["atlas-streams-build", "atlas-streams-manage"]
    build_args = invoker.calls[0][1]
    assert build_args["resource"] == "processor"
    assert build_args["pipeline"] == pipeline
    assert build_args["connection"] == "kafka-src"
    assert invoker.calls[1][1]["action"] == "start-processor"


async def test_lifecycle_ops_map_to_tools():
    invoker = FakeInvoker()
    conn = _connector(invoker)
    await conn.stop()
    await conn.diagnose()
    await conn.teardown()
    assert invoker.calls[0] == (
        "atlas-streams-manage",
        {"workspace": "ws", "name": "telemetry-proc", "action": "stop-processor"},
    )
    assert invoker.calls[1] == (
        "atlas-streams-discover",
        {"workspace": "ws", "name": "telemetry-proc", "action": "diagnose-processor"},
    )
    assert invoker.calls[2] == (
        "atlas-streams-teardown",
        {"workspace": "ws", "name": "telemetry-proc", "resource": "processor"},
    )


def test_extract_docs_variants():
    assert _extract_docs([{"a": 1}, "skip", {"b": 2}]) == [{"a": 1}, {"b": 2}]
    assert _extract_docs({"data": [{"x": 1}]}) == [{"x": 1}]
    assert _extract_docs({"k": "v"}) == [{"k": "v"}]
    block = {"content": [{"type": "text", "text": '[{"y": 9}]'}]}
    assert _extract_docs(block) == [{"y": 9}]
    plain = {"content": [{"type": "text", "text": "processor healthy"}]}
    assert _extract_docs(plain) == [{"text": "processor healthy"}]
    assert _extract_docs(None) == []
    assert _extract_docs({"content": []}) == []


def test_from_settings_uses_config_workspace_and_processor():
    settings = EzraSettings(
        atlas_streams_workspace="ws1", atlas_streams_processor="proc1"
    )
    invoker = FakeInvoker()
    conn = atlas_streams_connector_from_settings(
        settings, topics=["telemetry"], invoker=invoker
    )
    assert conn._workspace == "ws1"
    assert conn._processor == "proc1"


async def test_list_workspaces_is_project_scoped():
    invoker = FakeInvoker({"atlas-streams-discover": {"workspaces": [{"name": "w"}]}})
    conn = _connector(invoker)
    await conn.list_workspaces()
    tool, args = invoker.calls[0]
    assert tool == "atlas-streams-discover"
    # No workspace/name injected — list is project-scoped.
    assert args == {"action": "list-workspaces"}


async def test_project_id_is_threaded_into_calls():
    invoker = FakeInvoker()
    conn = AtlasStreamsConnector(
        invoker, workspace="ws", processor="p", project_id="proj-1", topics=["telemetry"]
    )
    await conn.list_workspaces()
    await conn.fetch("q", "a", ["telemetry"])
    # Both the project-scoped discover and the processor-scoped fetch carry projectId.
    assert invoker.calls[0][1] == {"action": "list-workspaces", "projectId": "proj-1"}
    assert invoker.calls[1][1]["projectId"] == "proj-1"


# --- McpHttpInvoker: the real Streamable-HTTP client (handshake + SSE) --------
def test_parse_jsonrpc_handles_json_and_sse():
    obj = {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
    assert _parse_jsonrpc("application/json", json.dumps(obj)) == obj
    sse = f"event: message\ndata: {json.dumps(obj)}\n\n"
    assert _parse_jsonrpc("text/event-stream", sse) == obj
    assert _parse_jsonrpc("application/json", "") == {}


def _mcp_mock_handler(captured: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        captured.setdefault("methods", []).append(body.get("method"))
        captured.setdefault("session_headers", []).append(
            request.headers.get("mcp-session-id")
        )
        captured.setdefault("proto_headers", []).append(
            request.headers.get("mcp-protocol-version")
        )
        method = body.get("method")
        if method == "initialize":
            return httpx.Response(
                200,
                headers={"mcp-session-id": "sess-xyz", "content-type": "application/json"},
                json={
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {"protocolVersion": "2025-06-18", "capabilities": {}},
                },
            )
        if method == "notifications/initialized":
            return httpx.Response(202)
        if method == "tools/call":
            captured["tool"] = body["params"]["name"]
            captured["args"] = body["params"]["arguments"]
            inner = {
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {
                    "content": [
                        {"type": "text", "text": json.dumps([{"name": "ws1"}])}
                    ]
                },
            }
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=f"event: message\ndata: {json.dumps(inner)}\n\n",
            )
        return httpx.Response(400)

    return handler


async def test_mcp_http_invoker_performs_handshake_then_call(monkeypatch):
    captured: dict = {}
    transport = httpx.MockTransport(_mcp_mock_handler(captured))
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: real_client(
            transport=transport, **{k: v for k, v in kw.items() if k != "transport"}
        ),
    )

    inv = McpHttpInvoker("http://mcp.test/mcp")
    result = await inv.call("atlas-streams-discover", {"action": "list-workspaces"})

    # initialize -> initialized ack -> tools/call, in order.
    assert captured["methods"] == ["initialize", "notifications/initialized", "tools/call"]
    # The session id from the initialize response header is sent on later requests.
    assert captured["session_headers"][0] is None  # initialize has no session yet
    assert captured["session_headers"][-1] == "sess-xyz"  # tools/call carries it
    # The protocol-version header is NOT sent on initialize, IS sent on tools/call.
    assert captured["proto_headers"][0] is None
    assert captured["proto_headers"][-1] == "2025-06-18"
    assert captured["tool"] == "atlas-streams-discover"
    # call() unwraps to the JSON-RPC result; _extract_docs then coerces the content.
    assert _extract_docs(result) == [{"name": "ws1"}]


async def test_mcp_http_invoker_raises_on_jsonrpc_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        if body.get("method") == "initialize":
            return httpx.Response(
                200,
                headers={"mcp-session-id": "s", "content-type": "application/json"},
                json={"jsonrpc": "2.0", "id": body["id"], "result": {"protocolVersion": "2025-06-18"}},
            )
        if body.get("method") == "notifications/initialized":
            return httpx.Response(202)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"jsonrpc": "2.0", "id": body["id"], "error": {"code": -32602, "message": "bad"}},
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: real_client(
            transport=transport, **{k: v for k, v in kw.items() if k != "transport"}
        ),
    )
    inv = McpHttpInvoker("http://mcp.test/mcp")
    with pytest.raises(RuntimeError):
        await inv.call("atlas-streams-discover", {"action": "list-workspaces"})
