"""RemoteEzraService — drive a deployed Ezra service over HTTP.

Exposes the scope-bound method surface (``recall / query / belief_snapshot /
commit / revert / rewind / branch_from / replay``); each call hits the Ezra REST
API. Responses parse back into the vendored wire models (:mod:`ezra_client.models`)
so caller code sees typed objects. Because it duck-types the platform's
``EzraService``, an :class:`ezra_client.EzraToolset` wraps it unchanged.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

import httpx

from ezra_client.errors import PolicyDeniedError, RemoteEzraError
from ezra_client.models import (
    BeliefSnapshot,
    Branch,
    Commitment,
    CommitResult,
    MeshResult,
    RewindResult,
    WarmSummary,
)


class RemoteEzraService:
    def __init__(
        self,
        base_url: str,
        *,
        session_graph_id: str,
        agent_id: str,
        permission_scope: list[str],
        bearer_token: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = 30.0,
    ) -> None:
        self.session_graph_id = session_graph_id
        self.agent_id = agent_id
        self.permission_scope = list(permission_scope)
        headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout
        )

    # -- internals -------------------------------------------------------- #
    def _base(self) -> dict:
        return {
            "session_graph_id": self.session_graph_id,
            "agent_id": self.agent_id,
            "scope": self.permission_scope,
        }

    async def _post(self, path: str, payload: dict) -> Any:
        resp = await self._client.post(path, json=payload)
        if resp.status_code == 403:
            detail = _detail(resp)
            raise PolicyDeniedError(_denied_topic(detail), self.permission_scope)
        if resp.status_code >= 400:
            raise RemoteEzraError(f"{resp.status_code}: {_detail(resp)}")
        return resp.json()

    # -- surface (mirrors EzraService) ------------------------------------ #
    async def recall(self, query: str, *, limit: int = 5) -> list[WarmSummary]:
        data = await self._post("/ezra/recall", {**self._base(), "query": query, "limit": limit})
        return [WarmSummary.model_validate(d) for d in data]

    async def belief_snapshot(self, *, as_of_turn: Optional[int] = None) -> BeliefSnapshot:
        payload = {"session_graph_id": self.session_graph_id, "scope": self.permission_scope}
        if as_of_turn is not None:
            payload["as_of_turn"] = as_of_turn
        return BeliefSnapshot.model_validate(await self._post("/ezra/belief/snapshot", payload))

    async def query(
        self, query: str, *, topics: Sequence[str] = (), as_of=None
    ) -> MeshResult:
        payload = {**self._base(), "query": query, "topics": list(topics)}
        return MeshResult.model_validate(await self._post("/ezra/mesh/query", payload))

    async def commit(
        self,
        claim: str,
        topic: str,
        *,
        turn_index: int,
        type: str = "decision",
        value: Any = None,
        trust_score: Optional[float] = None,
    ) -> CommitResult:
        payload = {
            **self._base(), "claim": claim, "topic": topic,
            "turn_index": turn_index, "type": type, "trust_score": trust_score,
        }
        return CommitResult.model_validate(await self._post("/ezra/commit", payload))

    async def revert(
        self, commitment_id: str, *, reason: str, turn_index: int
    ) -> Commitment:
        payload = {
            **self._base(), "commitment_id": commitment_id,
            "reason": reason, "turn_index": turn_index,
        }
        return Commitment.model_validate(await self._post("/ezra/revert", payload))

    async def rewind(self, turn: int, *, reason: str) -> RewindResult:
        payload = {**self._base(), "turn": turn, "reason": reason}
        return RewindResult.model_validate(await self._post("/ezra/rewind", payload))

    async def replay(self, turn: int) -> BeliefSnapshot:
        payload = {
            "session_graph_id": self.session_graph_id,
            "turn": turn,
            "scope": self.permission_scope,
        }
        return BeliefSnapshot.model_validate(await self._post("/ezra/replay", payload))

    async def branch_from(self, turn: int, branch_id: str, *, description: str = "") -> Branch:
        payload = {
            "session_graph_id": self.session_graph_id,
            "turn": turn,
            "branch_id": branch_id,
            "description": description or None,
        }
        return Branch.model_validate(await self._post("/ezra/branch", payload))

    async def aclose(self) -> None:
        await self._client.aclose()


def _detail(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("detail", resp.text))
    except Exception:  # noqa: BLE001
        return resp.text


def _denied_topic(detail: str) -> str:
    # PolicyDeniedError str() is "topic '<t>' not in scope ..."; recover <t>.
    if "'" in detail:
        return detail.split("'")[1]
    return detail
