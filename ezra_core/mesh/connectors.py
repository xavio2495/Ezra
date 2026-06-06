"""Real executors + from-settings builders for the warehouse connectors.

The ``SnowflakeConnector`` / ``BigQueryConnector`` take an injected ``executor``
(a ``Callable[[str], Awaitable[Any]]``) so they stay testable without live
credentials. These helpers wrap the real SDKs into such executors and run their
synchronous query APIs in a thread, so calling them from async code never blocks
the event loop. The SDK imports are lazy — importing this module stays cheap and
the lean API image (no warehouse SDKs) doesn't break.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from ezra_core.config import EzraSettings
from ezra_core.mesh.bigquery import BigQueryConnector
from ezra_core.mesh.snowflake import SnowflakeConnector
from ezra_core.mesh.translate import translator_from_settings


def snowflake_executor_from_settings(settings: EzraSettings):
    """An async executor that runs a SQL string against Snowflake (key-less:
    password auth from settings) and returns a list of row dicts."""

    def _execute(sql: str):
        import snowflake.connector

        conn = snowflake.connector.connect(
            account=settings.snowflake_account,
            user=settings.snowflake_user,
            password=settings.snowflake_password,
            role=settings.snowflake_role or None,
            warehouse=settings.snowflake_warehouse or None,
            database=settings.snowflake_database or None,
            schema=settings.snowflake_schema or None,
        )
        try:
            cur = conn.cursor()
            cur.execute(sql)
            cols = [c[0] for c in cur.description] if cur.description else []
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            conn.close()

    async def _run(sql: str):
        return await asyncio.to_thread(_execute, sql)

    return _run


def snowflake_connector_from_settings(
    settings: EzraSettings,
    table: str,
    *,
    topics: Optional[list[str]] = None,
    columns: Optional[dict[str, str]] = None,
) -> SnowflakeConnector:
    # A column allowlist enables NL→SQL translation (the LLM fills a validated
    # predicate; the connector owns FROM + time-travel). No columns → SELECT *.
    return SnowflakeConnector(
        table,
        executor=snowflake_executor_from_settings(settings),
        topics=topics,
        columns=columns,
        translator=translator_from_settings(settings) if columns else None,
    )


def bigquery_executor_from_settings(settings: EzraSettings):
    """An async executor that runs SQL against BigQuery (keyless via ADC /
    Workload Identity) and returns a list of row dicts."""

    def _execute(sql: str):
        from google.cloud import bigquery

        client = bigquery.Client(project=settings.bigquery_project or None)
        return [dict(row) for row in client.query(sql).result()]

    async def _run(sql: str):
        return await asyncio.to_thread(_execute, sql)

    return _run


def bigquery_connector_from_settings(
    settings: EzraSettings,
    table: str,
    *,
    topics: Optional[list[str]] = None,
    columns: Optional[dict[str, str]] = None,
) -> BigQueryConnector:
    return BigQueryConnector(
        table,
        executor=bigquery_executor_from_settings(settings),
        topics=topics,
        columns=columns,
        translator=translator_from_settings(settings) if columns else None,
    )
