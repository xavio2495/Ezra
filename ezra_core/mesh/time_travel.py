"""Universal time-travel helpers. Snowflake and BigQuery have native query-time
time-travel; MongoDB does not (see ``mongodb_mcp``)."""

from __future__ import annotations

from datetime import datetime


def snowflake_time_travel_clause(as_of: datetime) -> str:
    # SELECT ... FROM t AT (TIMESTAMP => '...'::timestamp_tz)
    return f"AT (TIMESTAMP => '{as_of.isoformat()}'::timestamp_tz)"


def bigquery_time_travel_clause(as_of: datetime) -> str:
    # SELECT ... FROM t FOR SYSTEM_TIME AS OF TIMESTAMP '...'
    return f"FOR SYSTEM_TIME AS OF TIMESTAMP '{as_of.isoformat()}'"
