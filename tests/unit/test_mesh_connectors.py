from datetime import datetime, timezone

import httpx

from ezra_core.mesh.bigquery import BigQueryConnector
from ezra_core.mesh.fastf1_adapter import FastF1Connector
from ezra_core.mesh.mongodb_mcp import MongoMcpConnector
from ezra_core.mesh.rest import RestConnector
from ezra_core.mesh.snowflake import SnowflakeConnector

AS_OF = datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc)


async def test_rest_connector_returns_typed_result_with_provenance():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "lead times"
        return httpx.Response(200, json={"lead_days": 14})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        connector = RestConnector("http://api.test/v1/leadtimes", client=client)
        result = await connector.fetch("lead times", "agent", ["logistics"])
    finally:
        await client.aclose()

    assert result.data == {"lead_days": 14}
    assert result.provenance.source.startswith("rest:")
    assert result.provenance.time_travel_available is False


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    async def __aiter__(self):
        for d in self._docs:
            yield d


class _FakeCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, filt):
        matched = [
            dict(d) for d in self._docs if all(d.get(k) == v for k, v in filt.items())
        ]
        return _FakeCursor(matched)


async def test_mongodb_connector_strips_id_and_no_time_travel():
    coll = _FakeCollection(
        [
            {"_id": 1, "part": "FW-07", "stock": 2},
            {"_id": 2, "part": "RW-03", "stock": 9},
        ]
    )
    connector = MongoMcpConnector(coll, source_name="inventory.parts")
    result = await connector.fetch('{"part": "FW-07"}', "agent", ["inventory"])

    assert result.data == [{"part": "FW-07", "stock": 2}]
    assert result.provenance.source == "mongodb:inventory.parts"
    assert result.provenance.time_travel_available is False


async def test_snowflake_time_travel_sql_and_provenance():
    captured = {}

    def executor(sql: str):
        captured["sql"] = sql
        return [{"stock": 2, "reorder_threshold": 5}]

    connector = SnowflakeConnector("warehouse.inventory", executor=executor)
    result = await connector.fetch("inventory below threshold", "a", ["inventory"], as_of=AS_OF)

    assert "AT (TIMESTAMP =>" in captured["sql"]
    assert result.data == [{"stock": 2, "reorder_threshold": 5}]
    assert result.provenance.time_travel_available is True
    assert result.provenance.source == "snowflake:warehouse.inventory"


async def test_snowflake_no_time_travel_clause_without_as_of():
    connector = SnowflakeConnector("warehouse.inventory")
    assert "AT (TIMESTAMP" not in connector.build_sql("q")


async def test_bigquery_time_travel_sql():
    captured = {}

    async def executor(sql: str):
        captured["sql"] = sql
        return [{"x": 1}]

    connector = BigQueryConnector("proj.ds.inventory", executor=executor)
    result = await connector.fetch("q", "a", ["inventory"], as_of=AS_OF)

    assert "FOR SYSTEM_TIME AS OF TIMESTAMP" in captured["sql"]
    assert result.data == [{"x": 1}]
    assert result.provenance.time_travel_available is True


async def test_fastf1_connector_uses_injected_source():
    connector = FastF1Connector(data_source=lambda q: {"lap": 12, "tyre": "soft"})
    result = await connector.fetch("current tyre", "race_eng", ["telemetry"])
    assert result.data == {"lap": 12, "tyre": "soft"}
    assert result.provenance.time_travel_available is False
