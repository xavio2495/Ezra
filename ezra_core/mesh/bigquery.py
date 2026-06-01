"""BigQuery connector — pushdown SQL with native time-travel via
``FOR SYSTEM_TIME AS OF``. Executes through an injected ``executor`` so the
connector is testable without live credentials.
"""

from __future__ import annotations

import inspect
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional, Union

from ezra_core.mesh.base import BaseConnector
from ezra_core.mesh.time_travel import bigquery_time_travel_clause
from ezra_core.schemas.mesh import MeshResult

Executor = Callable[[str], Union[Any, Awaitable[Any]]]


class BigQueryConnector(BaseConnector):
    time_travel_available = True

    def __init__(
        self,
        table: str,
        *,
        executor: Optional[Executor] = None,
        topics: Optional[list[str]] = None,
        synced_at: Optional[datetime] = None,
    ) -> None:
        self._table = table
        self._executor = executor
        self._topics = topics or []
        self._synced_at = synced_at

    def build_sql(self, query: str, as_of: Optional[datetime] = None) -> str:
        clause = f" {bigquery_time_travel_clause(as_of)}" if as_of else ""
        return f"SELECT * FROM `{self._table}`{clause}"

    async def fetch(
        self,
        query: str,
        agent_id: str,
        permission_scope: list[str],
        as_of: Optional[datetime] = None,
    ) -> MeshResult:
        sql = self.build_sql(query, as_of)
        data: Any = None
        if self._executor is not None:
            result = self._executor(sql)
            data = await result if inspect.isawaitable(result) else result

        return MeshResult(
            data=data,
            provenance=self._provenance(
                source=f"bigquery:{self._table}", synced_at=self._synced_at
            ),
            topics=self._topics,
        )
