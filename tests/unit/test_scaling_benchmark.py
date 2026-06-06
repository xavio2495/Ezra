from fakeredis import aioredis

from demo.scaling_benchmark import percentile, run_benchmark, summarise
from ezra_core.tiers.hot import HotTier


def test_percentile_endpoints_and_interpolation():
    assert percentile([], 50) == 0.0
    assert percentile([5.0], 99) == 5.0
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([1, 2, 3, 4], 0) == 1
    assert percentile([1, 2, 3, 4], 100) == 4


def test_summarise_reports_percentiles_and_sample_count():
    point = summarise(10, [10.0, 20.0, 30.0, 40.0])
    assert point.agent_count == 10
    assert point.samples == 4
    assert point.p50_ms == 25.0


async def test_run_benchmark_produces_one_point_per_count():
    hot = HotTier(aioredis.FakeRedis(decode_responses=True), max_turns=8)
    result = await run_benchmark(agent_counts=(1, 3), turns_per_agent=2, hot=hot)
    assert [p.agent_count for p in result.points] == [1, 3]
    assert all(p.samples > 0 for p in result.points)
    assert all(p.p99_ms >= p.p50_ms for p in result.points)


async def test_run_benchmark_runs_the_fleet_concurrently(monkeypatch):
    """The defining property: at a given count, agents are in flight at the same
    time — not serialised. A tracking LLM records the max concurrent in-flight."""
    import asyncio

    import demo.scaling_benchmark as sb

    state = {"inflight": 0, "max": 0}

    class TrackingLLM:
        async def complete(self, messages, **kwargs):
            state["inflight"] += 1
            state["max"] = max(state["max"], state["inflight"])
            await asyncio.sleep(0.01)
            state["inflight"] -= 1
            return "ack"

    monkeypatch.setattr(sb, "_InstantLLM", TrackingLLM)
    hot = HotTier(aioredis.FakeRedis(decode_responses=True), max_turns=8)
    await sb.run_benchmark(
        agent_counts=(5,), turns_per_agent=1, warmup_turns=0, hot=hot, concurrent=True
    )
    assert state["max"] >= 2  # multiple agents overlapped inside the router/LLM


async def test_run_benchmark_sequential_mode_does_not_overlap(monkeypatch):
    import asyncio

    import demo.scaling_benchmark as sb

    state = {"inflight": 0, "max": 0}

    class TrackingLLM:
        async def complete(self, messages, **kwargs):
            state["inflight"] += 1
            state["max"] = max(state["max"], state["inflight"])
            await asyncio.sleep(0.001)
            state["inflight"] -= 1
            return "ack"

    monkeypatch.setattr(sb, "_InstantLLM", TrackingLLM)
    hot = HotTier(aioredis.FakeRedis(decode_responses=True), max_turns=8)
    await sb.run_benchmark(
        agent_counts=(5,), turns_per_agent=1, warmup_turns=0, hot=hot, concurrent=False
    )
    assert state["max"] == 1  # one at a time
