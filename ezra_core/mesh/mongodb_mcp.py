"""MongoDB connector (Atlas via the official MCP server in production; here it
runs find/aggregate against an Atlas collection). MongoDB has NO query-time
time-travel — ``time_travel_available`` is always False, and ``as_of`` is
ignored. For historical state from MongoDB, use versioned-document patterns at
the application layer (Snowflake/BigQuery provide native query-time time-travel).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from ezra_core.mesh.base import BaseConnector
from ezra_core.mesh.translate import QueryTranslator
from ezra_core.schemas.mesh import MeshResult


class MongoMcpConnector(BaseConnector):
    time_travel_available = False

    def __init__(
        self,
        collection,
        *,
        source_name: str = "mongodb",
        limit: int = 50,
        topics: Optional[list[str]] = None,
        columns: Optional[dict[str, str]] = None,
        translator: Optional[QueryTranslator] = None,
    ) -> None:
        self._c = collection
        self._source = source_name
        self._limit = limit
        self._topics = topics or []
        # With columns+translator, NL intent → a validated find filter; otherwise
        # a literal JSON filter in the query string (or find-all).
        self._columns = columns or {}
        self._translator = translator

    @staticmethod
    def _parse_filter(query: str) -> dict:
        q = query.strip()
        if q.startswith("{"):
            try:
                return json.loads(q)
            except json.JSONDecodeError:
                return {}
        return {}

    def _filter_for(self, query: str) -> dict:
        if self._translator is not None and self._columns:
            return self._translator.to_mongo_filter(query, columns=self._columns)
        return self._parse_filter(query)

    async def fetch(
        self,
        query: str,
        agent_id: str,
        permission_scope: list[str],
        as_of: Optional[datetime] = None,
    ) -> MeshResult:
        filt = self._filter_for(query)
        cursor = self._c.find(filt).limit(self._limit)
        docs = []
        async for doc in cursor:
            doc.pop("_id", None)
            docs.append(doc)

        return MeshResult(
            data=docs,
            provenance=self._provenance(source=f"mongodb:{self._source}"),
            topics=self._topics,
        )
