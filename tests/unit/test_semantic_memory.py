from datetime import datetime, timezone

from ezra_core.memory.semantic import InMemorySemanticStore
from ezra_core.schemas.memory import SemanticFact


def _fact(
    fid: str,
    *,
    tier: str = "core",
    topics: list[str] | None = None,
    graphs: list[str] | None = None,
    user: str = "u1",
) -> SemanticFact:
    now = datetime.now(timezone.utc)
    return SemanticFact(
        id=fid,
        user_id=user,
        subject="s",
        predicate="p",
        object="o",
        tier=tier,
        topics=topics if topics is not None else ["tyres"],
        confidence=1.0,
        source_session_graph_ids=graphs or ["gA"],
        created_at=now,
        updated_at=now,
    )


async def test_get_core_filters_by_tier_scope_and_source():
    store = InMemorySemanticStore()
    await store.add(_fact("in", topics=["tyres"], graphs=["gA"]))
    await store.add(_fact("wrong_scope", topics=["fuel"], graphs=["gA"]))
    await store.add(_fact("wrong_graph", topics=["tyres"], graphs=["gZ"]))
    await store.add(_fact("archival", tier="archival", topics=["tyres"], graphs=["gA"]))

    core = await store.get_core(
        user_id="u1", scope_topics={"tyres"}, source_graph_ids=["gA"]
    )
    assert {f.id for f in core} == {"in"}


async def test_untopiced_fact_visible_to_any_scope():
    store = InMemorySemanticStore()
    await store.add(_fact("global", topics=[], graphs=["gA"]))
    core = await store.get_core(
        user_id="u1", scope_topics={"anything"}, source_graph_ids=["gA"]
    )
    assert {f.id for f in core} == {"global"}


async def test_superseded_fact_excluded():
    store = InMemorySemanticStore()
    f = _fact("old", graphs=["gA"])
    f.superseded_by = "new"
    await store.add(f)
    core = await store.get_core(
        user_id="u1", scope_topics={"tyres"}, source_graph_ids=["gA"]
    )
    assert core == []


async def test_increment_access():
    store = InMemorySemanticStore()
    await store.add(_fact("f", graphs=["gA"]))
    assert await store.increment_access("f") == 1
    assert await store.increment_access("f") == 2


async def test_user_isolation():
    store = InMemorySemanticStore()
    await store.add(_fact("mine", user="u1", graphs=["gA"]))
    await store.add(_fact("theirs", user="u2", graphs=["gA"]))
    core = await store.get_core(
        user_id="u1", scope_topics={"tyres"}, source_graph_ids=["gA"]
    )
    assert {f.id for f in core} == {"mine"}
