"""Stress test for the examples / SDK — drive the public surface hard under
concurrency and assert it stays correct:

  1. high-throughput concurrent write-back (no writes lost),
  2. many independent contradictions reconciled concurrently (each topic
     resolves to exactly one active claim),
  3. every example run many times in parallel on isolated runtimes (no errors).

These exercise the same SDK the examples use, at a scale the single-shot example
tests don't.
"""

import asyncio
import importlib

from examples._harness import build_offline_ezra

_EXAMPLES = [
    "basic_chat",
    "multi_agent_session_graph",
    "with_mongodb_source",
    "with_snowflake_source",
    "custom_reconciler",
    "branching_replay",
    "cross_graph_inheritance",
    "replay_session",
]


async def test_stress_high_throughput_concurrent_writes():
    # 20 agents x 10 commits, all in flight at once on one shared graph.
    ezra = build_offline_ezra(with_meta_agents=False, checker=None)
    try:
        graph = await ezra.create_session_graph(session_graph_id="stress-throughput")
        agents = [
            await ezra.spawn_agent(graph, agent_id=f"a{i}", permission_scope=[f"t{i}"])
            for i in range(20)
        ]

        async def drive(i, svc):
            for t in range(10):
                await svc.write_back(f"c-{i}-{t}", f"t{i}", turn_index=t + 1)

        await asyncio.gather(*(drive(i, svc) for i, svc in enumerate(agents)))
        active = await ezra.belief_store.get_active("stress-throughput")
        assert len(active) == 200  # every concurrent write landed; none lost
    finally:
        await ezra.aclose()


async def test_stress_concurrent_contradictions_resolve_per_topic():
    # K independent 2-agent contradictions run concurrently. Within each topic the
    # two commits are ordered (detection is point-in-time), so under
    # last_write_wins every topic must end with exactly the 2nd agent's claim.
    ezra = build_offline_ezra(checker="keyword")
    try:
        graph = await ezra.create_session_graph(
            session_graph_id="stress-contra", merge_strategy="last_write_wins"
        )
        K = 15
        pairs = []
        for k in range(K):
            a = await ezra.spawn_agent(graph, agent_id=f"a{k}", permission_scope=[f"t{k}"])
            b = await ezra.spawn_agent(graph, agent_id=f"b{k}", permission_scope=[f"t{k}"])
            pairs.append((k, a, b))

        async def contest(k, a, b):
            await a.commit(f"A-{k}", f"t{k}", turn_index=1)
            await b.commit(f"B-{k}", f"t{k}", turn_index=2)  # contradicts -> supersedes A

        await asyncio.gather(*(contest(k, a, b) for k, a, b in pairs))

        active = await ezra.belief_store.get_active("stress-contra")
        by_topic: dict[str, list[str]] = {}
        for c in active:
            by_topic.setdefault(c.topic, []).append(c.claim)
        assert len(by_topic) == K
        assert all(v == [f"B-{int(t[1:])}"] for t, v in by_topic.items())
    finally:
        await ezra.aclose()


async def test_stress_all_examples_run_in_parallel():
    # 5x each example, all concurrent, each on its own isolated runtime.
    mods = [importlib.import_module(f"examples.{n}") for n in _EXAMPLES]

    async def one(mod):
        ezra = build_offline_ezra()
        try:
            return await mod.run(ezra)
        finally:
            await ezra.aclose()

    coros = [one(mod) for _ in range(5) for mod in mods]
    results = await asyncio.gather(*coros, return_exceptions=True)

    errors = [r for r in results if isinstance(r, Exception)]
    assert not errors, errors[:3]
    assert len(results) == 5 * len(_EXAMPLES)
    assert all(isinstance(r, dict) and r for r in results)
