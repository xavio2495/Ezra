import pytest

from ezra_core.schemas.session_graph import SessionGraphState
from ezra_core.session_graph import InMemorySessionGraphStore, SessionGraph


async def _new_graph(**kwargs) -> tuple[SessionGraph, InMemorySessionGraphStore]:
    store = InMemorySessionGraphStore()
    graph = await SessionGraph.create(
        store=store, session_graph_id="g1", description="test", **kwargs
    )
    return graph, store


async def test_create_persists():
    graph, store = await _new_graph()
    assert graph.state is SessionGraphState.ACTIVE
    assert await store.get("g1") is not None


async def test_spawn_and_terminate_dynamically():
    graph, store = await _new_graph()
    await graph.spawn_agent(agent_id="a", permission_scope=["x"])
    await graph.spawn_agent(agent_id="b", permission_scope=["y"])
    assert {r.agent_id for r in graph.active_agents} == {"a", "b"}

    terminated = await graph.terminate_agent("a")
    assert terminated.terminated_at is not None
    assert {r.agent_id for r in graph.active_agents} == {"b"}
    assert {r.agent_id for r in graph.terminated_agents} == {"a"}


async def test_changes_are_persisted():
    graph, store = await _new_graph()
    await graph.spawn_agent(agent_id="a", permission_scope=["x"])
    await graph.terminate_agent("a")

    reloaded = await SessionGraph.load("g1", store)
    assert reloaded.active_agents == []
    assert {r.agent_id for r in reloaded.terminated_agents} == {"a"}


async def test_duplicate_active_agent_rejected():
    graph, _ = await _new_graph()
    await graph.spawn_agent(agent_id="a", permission_scope=[])
    with pytest.raises(ValueError):
        await graph.spawn_agent(agent_id="a", permission_scope=[])


async def test_terminate_unknown_agent_raises():
    graph, _ = await _new_graph()
    with pytest.raises(KeyError):
        await graph.terminate_agent("nope")


async def test_custom_strategy_requires_resolver():
    store = InMemorySessionGraphStore()
    with pytest.raises(ValueError):
        await SessionGraph.create(
            store=store, session_graph_id="g2", merge_strategy="custom"
        )


async def test_load_missing_raises():
    store = InMemorySessionGraphStore()
    with pytest.raises(KeyError):
        await SessionGraph.load("missing", store)
