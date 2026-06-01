"""Generic HTTP/JSON connector. Limited pushdown; time-travel is source-
dependent (reported as unavailable by default)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx

from ezra_core.mesh.base import BaseConnector
from ezra_core.schemas.mesh import MeshResult


class RestConnector(BaseConnector):
    time_travel_available = False

    def __init__(
        self,
        url: str,
        *,
        method: str = "GET",
        client: Optional[httpx.AsyncClient] = None,
        query_param: str = "q",
        topics: Optional[list[str]] = None,
    ) -> None:
        self._url = url
        self._method = method
        self._client = client
        self._query_param = query_param
        self._topics = topics or []

    async def fetch(
        self,
        query: str,
        agent_id: str,
        permission_scope: list[str],
        as_of: Optional[datetime] = None,
    ) -> MeshResult:
        client = self._client or httpx.AsyncClient()
        owns_client = self._client is None
        try:
            resp = await client.request(
                self._method, self._url, params={self._query_param: query}
            )
            resp.raise_for_status()
            data = resp.json()
        finally:
            if owns_client:
                await client.aclose()

        return MeshResult(
            data=data,
            provenance=self._provenance(source=f"rest:{self._url}"),
            topics=self._topics,
        )
