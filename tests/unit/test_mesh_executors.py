"""Unit tests for the warehouse executor wrappers (connectors.py).

The real SDKs aren't called — we monkeypatch them — so these stay network-free.
They check that a SQL string runs through the executor and rows come back as dicts,
and that the executor plugs into the SnowflakeConnector to produce a typed
MeshResult with time_travel_available=true.
"""

import sys
import types

from ezra_core.config import EzraSettings
from ezra_core.mesh.connectors import (
    snowflake_connector_from_settings,
    snowflake_executor_from_settings,
)


class _FakeCursor:
    def __init__(self, rows, description):
        self._rows = rows
        self.description = description
        self.executed = None

    def execute(self, sql):
        self.executed = sql

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows, description):
        self._cur = _FakeCursor(rows, description)
        self.closed = False

    def cursor(self):
        return self._cur

    def close(self):
        self.closed = True


def _install_fake_snowflake(monkeypatch, rows, description):
    captured = {}

    def connect(**kwargs):
        captured["kwargs"] = kwargs
        captured["conn"] = _FakeConn(rows, description)
        return captured["conn"]

    fake_connector = types.ModuleType("snowflake.connector")
    fake_connector.connect = connect
    fake_pkg = types.ModuleType("snowflake")
    fake_pkg.connector = fake_connector
    monkeypatch.setitem(sys.modules, "snowflake", fake_pkg)
    monkeypatch.setitem(sys.modules, "snowflake.connector", fake_connector)
    return captured


async def test_snowflake_executor_maps_rows_to_dicts(monkeypatch):
    captured = _install_fake_snowflake(
        monkeypatch,
        rows=[(2023, "VER"), (2023, "PER")],
        description=[("SEASON",), ("DRIVER",)],
    )
    settings = EzraSettings(snowflake_account="acc", snowflake_user="u", snowflake_password="p")
    execute = snowflake_executor_from_settings(settings)
    out = await execute("SELECT season, driver FROM t")

    assert out == [{"SEASON": 2023, "DRIVER": "VER"}, {"SEASON": 2023, "DRIVER": "PER"}]
    assert captured["kwargs"]["account"] == "acc"
    assert captured["conn"].closed  # connection always closed


async def test_snowflake_connector_returns_typed_result_with_time_travel(monkeypatch):
    _install_fake_snowflake(
        monkeypatch, rows=[(1, "VER")], description=[("ROUND",), ("DRIVER",)]
    )
    settings = EzraSettings(snowflake_account="acc", snowflake_user="u", snowflake_password="p")
    connector = snowflake_connector_from_settings(
        settings, "EZRA.PUBLIC.RACE_RESULTS", topics=["strategy"]
    )
    result = await connector.fetch("recent results", "strategist", ["strategy"])

    assert result.provenance.time_travel_available is True
    assert result.provenance.source == "snowflake:EZRA.PUBLIC.RACE_RESULTS"
    assert result.data == [{"ROUND": 1, "DRIVER": "VER"}]
    assert result.topics == ["strategy"]
