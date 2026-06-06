"""Scaling benchmark — 1 → 50 *concurrent* agents in one session graph.

Measures per-agent router overhead (context assembly + tier reads + write-back)
across a growing fleet and reports the p50/p99 curve. Every agent in a fleet runs
its turns **concurrently** (``asyncio.gather``) so the measured latency reflects
real contention on the shared event loop + tiers at that scale — not isolated
per-call timing. The benchmark uses a near-instant fake agent LLM so the measured
time is the *router overhead*, not model latency — matching the calibrated SLA
wording (p50 <40ms / p99 <100ms per-agent overhead, excluding the LLM call, at
5–100 agents).

``percentile`` and ``summarise`` are pure and unit-tested; ``run_benchmark``
accepts an injected ``HotTier`` so tests can drive it with fakeredis.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from math import ceil, floor
from typing import Optional, Sequence

from pydantic import BaseModel, Field

from ezra_core.belief.store import InMemoryBeliefStore
from ezra_core.router import Router
from ezra_core.schemas.session_graph import AgentRegistration
from ezra_core.tiers.hot import HotTier


class _InstantLLM:
    async def complete(self, messages, **kwargs):
        return "ack"


def percentile(values: Sequence[float], p: float) -> float:
    """Linear-interpolation percentile (p in [0, 100])."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * (p / 100.0)
    lo, hi = floor(k), ceil(k)
    if lo == hi:
        return ordered[int(k)]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


class ScalingPoint(BaseModel):
    agent_count: int
    p50_ms: float
    p99_ms: float
    samples: int


class BenchmarkResult(BaseModel):
    points: list[ScalingPoint] = Field(default_factory=list)

    @property
    def flat(self) -> bool:
        """True if p99 never blows up across the curve (max ≤ 3× min)."""
        p99s = [pt.p99_ms for pt in self.points]
        return bool(p99s) and max(p99s) <= 3 * max(min(p99s), 1e-6)


def summarise(agent_count: int, latencies_ms: Sequence[float]) -> ScalingPoint:
    return ScalingPoint(
        agent_count=agent_count,
        p50_ms=round(percentile(latencies_ms, 50), 3),
        p99_ms=round(percentile(latencies_ms, 99), 3),
        samples=len(latencies_ms),
    )


def _agent(graph_id: str, i: int) -> AgentRegistration:
    return AgentRegistration(
        agent_id=f"agent-{i}",
        session_graph_id=graph_id,
        permission_scope=["telemetry"],
        spawned_at=datetime.now(timezone.utc),
    )


async def run_benchmark(
    *,
    agent_counts: Sequence[int] = (1, 5, 10, 25, 50),
    turns_per_agent: int = 3,
    warmup_turns: int = 5,
    hot: Optional[HotTier] = None,
    graph_id: str = "scaling-benchmark",
    concurrent: bool = True,
) -> BenchmarkResult:
    if hot is None:  # pragma: no cover - real-redis path used by the script main
        import redis.asyncio as aioredis

        from ezra_core.config import EzraSettings

        settings = EzraSettings()
        hot = HotTier(aioredis.from_url(settings.redis_url, decode_responses=True))

    # Warm up one-time process costs (Redis connect, import/JIT) so the first
    # measured count isn't penalised by a cold start.
    warmup_router = Router(hot=hot, belief_store=InMemoryBeliefStore(), llm=_InstantLLM())
    for _ in range(warmup_turns):
        await warmup_router.run_turn(agent=_agent(graph_id, -1), user_input="warmup")

    async def _drive(router: Router, agent) -> list[float]:
        """One agent's turns; returns the per-turn router-overhead latencies (ms)."""
        local: list[float] = []
        for _ in range(turns_per_agent):
            start = time.perf_counter()
            await router.run_turn(agent=agent, user_input="status?")
            local.append((time.perf_counter() - start) * 1000.0)
        return local

    result = BenchmarkResult()
    for count in agent_counts:
        router = Router(hot=hot, belief_store=InMemoryBeliefStore(), llm=_InstantLLM())
        agents = [_agent(graph_id, i) for i in range(count)]
        latencies: list[float] = []
        if concurrent:
            # All `count` agents run their turns at once — the latency each turn
            # sees now includes contention from the rest of the fleet.
            per_agent = await asyncio.gather(*(_drive(router, a) for a in agents))
            for lst in per_agent:
                latencies.extend(lst)
        else:
            for agent in agents:
                latencies.extend(await _drive(router, agent))
        result.points.append(summarise(count, latencies))
    return result
