from datetime import datetime, timezone

from ezra_core.memory.semantic import InMemorySemanticStore
from ezra_core.schemas.memory import SemanticFact


class FakeEmbedder:
    """Clusters onto two axes by keyword (deterministic)."""

    def encode(self, text):
        return [1.0, 0.0] if "tyre" in text.lower() else [0.0, 1.0]


def _fact(
    fid: str,
    *,
    tier: str = "core",
    topics: list[str] | None = None,
    graphs: list[str] | None = None,
    user: str = "u1",
    subject: str = "s",
    predicate: str = "p",
    object: str = "o",
) -> SemanticFact:
    now = datetime.now(timezone.utc)
    return SemanticFact(
        id=fid,
        user_id=user,
        subject=subject,
        predicate=predicate,
        object=object,
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


async def test_add_embeds_fact_when_embedder_present():
    store = InMemorySemanticStore(FakeEmbedder())
    await store.add(_fact("f", subject="tyre", predicate="wear", object="high"))
    stored = await store.get("f")
    assert stored.embedding == [1.0, 0.0]


async def test_recall_archival_ranks_by_similarity_and_scope():
    store = InMemorySemanticStore(FakeEmbedder())
    await store.add(_fact("tyre-fact", tier="archival", topics=["tyres"], subject="tyre"))
    await store.add(_fact("fuel-fact", tier="archival", topics=["fuel"], subject="fuel"))
    # core fact is excluded; only archival is recalled
    await store.add(_fact("tyre-core", tier="core", topics=["tyres"], subject="tyre"))

    hits = await store.recall_archival(
        "tyre degradation question", user_id="u1", scope_topics={"tyres"}, limit=5
    )
    assert [f.id for f in hits] == ["tyre-fact"]  # fuel out of scope, core excluded


async def test_recall_archival_user_isolation():
    store = InMemorySemanticStore(FakeEmbedder())
    await store.add(_fact("mine", tier="archival", user="u1", subject="tyre"))
    await store.add(_fact("theirs", tier="archival", user="u2", subject="tyre"))
    hits = await store.recall_archival(
        "tyre", user_id="u1", scope_topics={"tyres"}, limit=5
    )
    assert {f.id for f in hits} == {"mine"}


async def test_recall_archival_without_embedder_returns_empty():
    store = InMemorySemanticStore()  # no embedder
    await store.add(_fact("f", tier="archival", subject="tyre"))
    hits = await store.recall_archival(
        "tyre", user_id="u1", scope_topics={"tyres"}, limit=5
    )
    assert hits == []
