"""Hot tier — per-agent state in Redis.

Each agent has its own keys (O(1) per agent; adding agents adds keys, not
iterations). Holds the agent's recent turns, pinned beliefs, and the current
mesh result. Values are JSON; construct the Redis client with
``decode_responses=True``.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from redis.asyncio import Redis

from ezra_core.config import EzraSettings


class HotTier:
    def __init__(self, redis: Redis, max_turns: int = 8) -> None:
        self._r = redis
        self._max_turns = max_turns

    def _prefix(self, session_graph_id: str, agent_id: str) -> str:
        return f"ezra:hot:{session_graph_id}:{agent_id}"

    def _turns_key(self, g: str, a: str) -> str:
        return f"{self._prefix(g, a)}:turns"

    def _pinned_key(self, g: str, a: str) -> str:
        return f"{self._prefix(g, a)}:pinned"

    def _mesh_key(self, g: str, a: str) -> str:
        return f"{self._prefix(g, a)}:mesh"

    # -- turns (capped at max_turns, oldest evicted) --------------------- #
    async def append_turn(self, session_graph_id: str, agent_id: str, turn: dict[str, Any]) -> None:
        key = self._turns_key(session_graph_id, agent_id)
        await self._r.rpush(key, json.dumps(turn))
        await self._r.ltrim(key, -self._max_turns, -1)

    async def get_turns(self, session_graph_id: str, agent_id: str) -> list[dict[str, Any]]:
        raw = await self._r.lrange(self._turns_key(session_graph_id, agent_id), 0, -1)
        return [json.loads(item) for item in raw]

    # -- pinned beliefs --------------------------------------------------- #
    async def set_pinned_beliefs(
        self, session_graph_id: str, agent_id: str, beliefs: list[dict[str, Any]]
    ) -> None:
        await self._r.set(self._pinned_key(session_graph_id, agent_id), json.dumps(beliefs))

    async def get_pinned_beliefs(self, session_graph_id: str, agent_id: str) -> list[dict[str, Any]]:
        raw = await self._r.get(self._pinned_key(session_graph_id, agent_id))
        return json.loads(raw) if raw else []

    # -- current mesh result --------------------------------------------- #
    async def set_mesh_result(
        self, session_graph_id: str, agent_id: str, result: dict[str, Any]
    ) -> None:
        await self._r.set(self._mesh_key(session_graph_id, agent_id), json.dumps(result))

    async def get_mesh_result(
        self, session_graph_id: str, agent_id: str
    ) -> Optional[dict[str, Any]]:
        raw = await self._r.get(self._mesh_key(session_graph_id, agent_id))
        return json.loads(raw) if raw else None

    async def clear_agent(self, session_graph_id: str, agent_id: str) -> None:
        await self._r.delete(
            self._turns_key(session_graph_id, agent_id),
            self._pinned_key(session_graph_id, agent_id),
            self._mesh_key(session_graph_id, agent_id),
        )


def hot_tier_from_settings(settings: EzraSettings) -> HotTier:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return HotTier(redis, max_turns=settings.hot_max_turns)
