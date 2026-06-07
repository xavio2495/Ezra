# Federated Query

Ezra never pulls raw data into memory and hands it to an agent. It translates intent into a **native, constrained query**, executes it **at the storage layer**, and injects a typed summary with provenance.

## Pushdown execution

The database does the math — MongoDB aggregation, Snowflake SQL, BigQuery SQL, Atlas Stream Processing, REST. The agent receives a typed `MeshResult`, never a raw dump.

## Typed provenance

Every injected fact carries `{ source, synced_at, field_types, confidence, time_travel_available, queried_at }`. Crucially, `time_travel_available` tells the caller whether the result came from a source that supports query-time time-travel.

## Intent → native query, safely

When a connector is given a column allowlist and a translator, an LLM turns the natural-language intent into a **validated** pushdown predicate — but it only fills validated slots. The projection must be ⊆ the allowlist, the `WHERE` may only reference allowlisted columns, and `;` / DDL / DML / subqueries are rejected; `LIMIT` is clamped. The connector itself owns the `FROM` clause and time-travel. Anything suspect falls back to a safe `SELECT *`. **Free-form model output is never executed.**

```python
from ezra_core.mesh.connectors import snowflake_connector_from_settings

columns = {"SEASON": "int", "DRIVER": "str", "CONSTRUCTOR": "str", "POSITION": "int"}
conn = snowflake_connector_from_settings(
    settings, "EZRA.PUBLIC.RACE_RESULTS", topics=["strategy"], columns=columns,
)
# "all race results from the 2023 season"
#   → SELECT … FROM EZRA.PUBLIC.RACE_RESULTS WHERE SEASON = 2023 LIMIT 100
result = await conn.fetch("all race results from the 2023 season", "race_strategy", ["strategy"])
```

## Giving an agent data access

Pass a connector as `mesh=` when spawning; the router's step 5 fetches through it (policy-gated) when intent requires:

```python
agent = await ezra.spawn_agent(
    graph, agent_id="race_strategy", permission_scope=["strategy"], mesh=conn,
)
```

## Connectors

| Connector               | Source                          | Time-travel                       | Builder                                 |
| ----------------------- | ------------------------------- | --------------------------------- | --------------------------------------- |
| `MongoMcpConnector`     | MongoDB Atlas (via MongoDB MCP) | no                                | `mongodb_mcp.py`                        |
| `AtlasStreamsConnector` | Atlas Stream Processing         | no                                | `atlas_streams_connector_from_settings` |
| `SnowflakeConnector`    | Snowflake                       | **yes** — `AT (TIMESTAMP => …)`   | `snowflake_connector_from_settings`     |
| `BigQueryConnector`     | BigQuery                        | **yes** — `FOR SYSTEM_TIME AS OF` | `bigquery_connector_from_settings`      |
| `RestConnector`         | any REST API                    | no                                | `rest.py`                               |
| `FastF1Connector`       | F1 timing (demo)                | no                                | `fastf1_adapter.py`                     |

MongoDB has no query-time time-travel (PITR is backup-restore, not a query primitive), so its connectors return `time_travel_available=false` and ignore `as_of`. Snowflake/BigQuery support it natively.

## Atlas Stream Processing (MongoDB MCP)

Live telemetry flows through Atlas Stream Processing, reached via MongoDB MCP's `atlas-streams-*` tools. `AtlasStreamsConnector` wraps `build` / `discover` / `manage` / `teardown` behind an injected invoker; `McpHttpInvoker` speaks the full MCP Streamable-HTTP lifecycle (`initialize` → `Mcp-Session-Id` → `notifications/initialized` → `tools/call`, JSON or SSE). The `atlas-streams-*` tools are project-scoped, so the connector threads the Atlas `projectId`.

```python
from ezra_core.mesh.atlas_streams import atlas_streams_connector_from_settings

streams = atlas_streams_connector_from_settings(settings, topics=["telemetry"])
await streams.fetch("current telemetry posture", "telemetry_analyst", ["telemetry"])
```

## Time-travel federated query

Ezra-state time-travel is always available (Ezra controls its own snapshots — see [Branching](/docs/branching)). Source-side time-travel is best-effort and source-dependent; provenance's `time_travel_available` flag tells you which kind of result you got.
