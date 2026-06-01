"""FastF1 connector (demo only — exercised by the F1 reference demo, Session 5).

Limited pushdown, no time-travel. The telemetry source is injected so the heavy
``fastf1`` package is never imported by the platform package itself; the demo
wires a real FastF1-backed callable.
"""

from __future__ import annotations

import inspect
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional, Union

from ezra_core.mesh.base import BaseConnector
from ezra_core.schemas.mesh import MeshResult

DataSource = Callable[[str], Union[Any, Awaitable[Any]]]


class FastF1Connector(BaseConnector):
    time_travel_available = False

    def __init__(
        self,
        *,
        data_source: Optional[DataSource] = None,
        topics: Optional[list[str]] = None,
    ) -> None:
        self._data_source = data_source
        self._topics = topics or []

    async def fetch(
        self,
        query: str,
        agent_id: str,
        permission_scope: list[str],
        as_of: Optional[datetime] = None,
    ) -> MeshResult:
        data: Any = {}
        if self._data_source is not None:
            result = self._data_source(query)
            data = await result if inspect.isawaitable(result) else result

        return MeshResult(
            data=data,
            provenance=self._provenance(source="fastf1"),
            topics=self._topics,
        )
