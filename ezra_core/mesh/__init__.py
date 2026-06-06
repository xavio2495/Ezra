"""Federated query connectors. Built-in: MongoDB MCP, Atlas Stream Processing,
REST, Snowflake, BigQuery, FastF1 (demo)."""

from ezra_core.mesh.atlas_streams import AtlasStreamsConnector
from ezra_core.mesh.base import BaseConnector
from ezra_core.mesh.bigquery import BigQueryConnector
from ezra_core.mesh.fastf1_adapter import FastF1Connector
from ezra_core.mesh.mongodb_mcp import MongoMcpConnector
from ezra_core.mesh.rest import RestConnector
from ezra_core.mesh.snowflake import SnowflakeConnector

__all__ = [
    "BaseConnector",
    "MongoMcpConnector",
    "AtlasStreamsConnector",
    "RestConnector",
    "SnowflakeConnector",
    "BigQueryConnector",
    "FastF1Connector",
]
