import json

from ezra_core.mesh.atlas_streams import (
    AtlasStreamsConnector,
    _extract_docs,
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
