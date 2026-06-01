from datetime import datetime, timezone

from ezra_core.memory.procedural import InMemoryProceduralStore
from ezra_core.memory.semantic import InMemorySemanticStore
from ezra_core.router import hydrate_at_agent_spawn
from ezra_core.schemas.memory import ProceduralRule, SemanticFact
from ezra_core.schemas.session_graph import AgentRegistration
from ezra_core.schemas.session_graph import SessionGraph as SessionGraphRecord


def _now():
    return datetime.now(timezone.utc)


def _fact(fid, *, topics, graphs, tier="core", user="u1"):
    return SemanticFact(
        id=fid,
        user_id=user,
        subject="s",
        predicate="p",
        object="o",
        tier=tier,
        topics=topics,
        confidence=1.0,
        source_session_graph_ids=graphs,
        created_at=_now(),
        updated_at=_now(),
    )


def _graph_b(*, inherit_procedural=True) -> SessionGraphRecord:
    return SessionGraphRecord(
        session_graph_id="gB",
        created_at=_now(),
        inherits_from=["gA"],
        inherit_procedural=inherit_procedural,
    )


def _agent(scope) -> AgentRegistration:
    return AgentRegistration(
        agent_id="strategist",
        session_graph_id="gB",
        permission_scope=scope,
        spawned_at=_now(),
    )


async def test_hydrate_loads_own_and_inherited_core_scope_filtered():
    semantic = InMemorySemanticStore()
    await semantic.add(_fact("own", topics=["tyres"], graphs=["gB"]))
    await semantic.add(_fact("inherited", topics=["tyres"], graphs=["gA"]))
    await semantic.add(_fact("out_of_scope", topics=["fuel"], graphs=["gA"]))

    h = await hydrate_at_agent_spawn(
        graph=_graph_b(),
        agent=_agent(["tyres"]),
        user_id="u1",
        semantic_store=semantic,
    )

    assert {f.id for f in h.own_core} == {"own"}
    assert {f.id for f in h.inherited_core} == {"inherited"}
    assert {f.id for f in h.all_core} == {"own", "inherited"}


async def test_procedural_inherited_when_enabled():
    semantic = InMemorySemanticStore()
    procedural = InMemoryProceduralStore()
    await procedural.add(
        ProceduralRule(
            id="r1",
            user_id="u1",
            pattern="pit-window",
            rule="pit under VSC",
            topics=["tyres"],
            source_session_graph_ids=["gA"],
            confidence=0.9,
            created_at=_now(),
        )
    )

    enabled = await hydrate_at_agent_spawn(
        graph=_graph_b(inherit_procedural=True),
        agent=_agent(["tyres"]),
        user_id="u1",
        semantic_store=semantic,
        procedural_store=procedural,
    )
    assert {r.id for r in enabled.inherited_procedural} == {"r1"}

    disabled = await hydrate_at_agent_spawn(
        graph=_graph_b(inherit_procedural=False),
        agent=_agent(["tyres"]),
        user_id="u1",
        semantic_store=semantic,
        procedural_store=procedural,
    )
    assert disabled.inherited_procedural == []
