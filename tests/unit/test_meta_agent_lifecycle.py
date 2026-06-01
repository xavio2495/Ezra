from datetime import datetime, timedelta, timezone

from ezra_core.belief.store import InMemoryBeliefStore
from ezra_core.meta_agent.lifecycle import LifecycleMetaAgent
from ezra_core.schemas.belief import Commitment
from ezra_core.schemas.session_graph import SessionGraphState
from ezra_core.session_graph import InMemorySessionGraphStore, SessionGraph


class FakeWarm:
    def __init__(self):
        self.evicted = False

    async def evict_expired(self, *, now=None):
        self.evicted = True


def _commit(cid, *, created_at, topic="parts"):
    return Commitment(
        id=cid,
        session_graph_id="race-1",
        agent_id="parts",
        turn_index=1,
        type="fact",
        claim="stock critical",
        topic=topic,
        created_at=created_at,
    )


async def _graph(store, **kwargs):
    return await SessionGraph.create(store=store, session_graph_id="race-1", **kwargs)


async def test_close_if_idle_transitions_active_to_closed_when_empty():
    store = InMemorySessionGraphStore()
    graph = await _graph(store)
    await graph.spawn_agent(agent_id="parts", permission_scope=["parts"])
    agent = LifecycleMetaAgent(store)

    assert await agent.close_if_idle("race-1") is False  # an agent is still active

    await graph.terminate_agent("parts")
    assert await agent.close_if_idle("race-1") is True
    assert (await store.get("race-1")).state == SessionGraphState.CLOSED


async def test_archive_if_stale_only_after_threshold():
    store = InMemorySessionGraphStore()
    await _graph(store, archival_threshold_days=90)
    agent = LifecycleMetaAgent(store)

    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert await agent.close_if_idle("race-1", now=t0) is True

    assert await agent.archive_if_stale("race-1", now=t0 + timedelta(days=10)) is False
    assert await agent.archive_if_stale("race-1", now=t0 + timedelta(days=91)) is True
    assert (await store.get("race-1")).state == SessionGraphState.ARCHIVED


async def test_enforce_belief_retention_tombstones_old_commitments():
    store = InMemorySessionGraphStore()
    await _graph(store, belief_retention_days=30)
    belief = InMemoryBeliefStore()
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    await belief.append(_commit("old", created_at=now - timedelta(days=45)))
    await belief.append(_commit("recent", created_at=now - timedelta(days=5)))
    agent = LifecycleMetaAgent(store, belief_store=belief)

    tombstoned = await agent.enforce_belief_retention("race-1", now=now)

    assert tombstoned == ["old"]
    assert (await belief.get("old")).redacted is True
    assert (await belief.get("recent")).redacted is False


async def test_belief_retention_noop_when_infinite():
    store = InMemorySessionGraphStore()
    await _graph(store)  # belief_retention_days defaults to None = infinite
    belief = InMemoryBeliefStore()
    await belief.append(_commit("old", created_at=datetime(2000, 1, 1, tzinfo=timezone.utc)))
    agent = LifecycleMetaAgent(store, belief_store=belief)

    assert await agent.enforce_belief_retention("race-1") == []
    assert (await belief.get("old")).redacted is False


async def test_apply_tombstone_redacts_for_gdpr():
    store = InMemorySessionGraphStore()
    belief = InMemoryBeliefStore()
    await belief.append(_commit("c1", created_at=datetime.now(timezone.utc)))
    agent = LifecycleMetaAgent(store, belief_store=belief)

    await agent.apply_tombstone("c1", "gdpr-erasure-request")
    c = await belief.get("c1")
    assert c.redacted is True
    assert c.redaction_reason == "gdpr-erasure-request"


async def test_tick_runs_full_scheduled_pass():
    store = InMemorySessionGraphStore()
    await _graph(store, belief_retention_days=30)
    belief = InMemoryBeliefStore()
    warm = FakeWarm()
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    await belief.append(_commit("old", created_at=now - timedelta(days=60)))
    agent = LifecycleMetaAgent(store, belief_store=belief, warm=warm)

    report = await agent.tick("race-1", now=now)

    assert report.transition == "closed"  # freshly created graph, no active agents
    assert report.tombstoned_commitment_ids == ["old"]
    assert report.evicted_warm is True
    assert warm.evicted is True
