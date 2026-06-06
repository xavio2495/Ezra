"""Router step 1 (Parse) + intent-driven step 5 (Fetch).

Covers the heuristic parser's fetch detection and the router's intent-driven
auto-fetch: it fetches via the connector when the parser flags needs_fetch,
skips when it doesn't, still honours an explicit mesh_query, and degrades safely
when an inferred fetch is policy-denied.
"""

from datetime import datetime, timezone

from fakeredis import aioredis

from ezra_core.belief.store import InMemoryBeliefStore
from ezra_core.parse import HeuristicIntentParser, ParsedIntent
from ezra_core.policy.engine import PolicyEngine
from ezra_core.router import Router
from ezra_core.schemas.context import ContextSlotType
from ezra_core.schemas.mesh import MeshResult, Provenance
from ezra_core.schemas.session_graph import AgentRegistration
from ezra_core.tiers.hot import HotTier


class FakeLLM:
    async def complete(self, messages, **kwargs):
        return "ok"


class RecordingConnector:
    """Records the query it was asked to fetch; returns a canned MeshResult."""

    time_travel_available = False

    def __init__(self):
        self.calls = []

    async def fetch(self, query, agent_id, permission_scope, as_of=None):
        self.calls.append(query)
        return MeshResult(
            data=[{"x": 1}],
            provenance=Provenance(source="fake", queried_at=datetime.now(timezone.utc)),
            topics=["telemetry"],
        )


class StubParser:
    def __init__(self, intent):
        self._intent = intent

    def parse(self, user_input, *, scope=()):
        return self._intent


def _agent(scope=("telemetry",)):
    return AgentRegistration(
        agent_id="a", session_graph_id="g",
        permission_scope=list(scope), spawned_at=datetime.now(timezone.utc),
    )


async def _router(**kw):
    hot = HotTier(aioredis.FakeRedis(decode_responses=True))
    return Router(hot=hot, belief_store=InMemoryBeliefStore(), llm=FakeLLM(), **kw)


# -- heuristic parser ------------------------------------------------------ #
def test_heuristic_flags_fetch_on_data_seeking_input():
    p = HeuristicIntentParser()
    assert p.parse("what are the latest telemetry results?", scope=["telemetry"]).needs_fetch
    assert p.parse("let's brainstorm a strategy", scope=["telemetry"]).needs_fetch is False


def test_heuristic_selects_in_scope_topics():
    p = HeuristicIntentParser()
    parsed = p.parse("show me the current tyre data", scope=["tyres", "fuel"])
    assert "tyres" in parsed.topics


# -- intent-driven fetch --------------------------------------------------- #
async def test_router_auto_fetches_when_parser_says_fetch():
    conn = RecordingConnector()
    parser = StubParser(ParsedIntent(needs_fetch=True, topics=["telemetry"]))
    router = await _router(mesh=conn, parser=parser)

    result = await router.run_turn(agent=_agent(), user_input="latest telemetry?")
    assert conn.calls == ["latest telemetry?"]  # NL passed to the connector
    assert result.mesh_result is not None
    assert result.parsed_intent.needs_fetch is True
    assert any(s.slot_type == ContextSlotType.MESH_RESULT for s in result.context.slots)


async def test_router_skips_fetch_when_parser_says_no():
    conn = RecordingConnector()
    parser = StubParser(ParsedIntent(needs_fetch=False))
    router = await _router(mesh=conn, parser=parser)

    result = await router.run_turn(agent=_agent(), user_input="just reasoning")
    assert conn.calls == []
    assert result.mesh_result is None


async def test_explicit_mesh_query_bypasses_parser():
    conn = RecordingConnector()
    parser = StubParser(ParsedIntent(needs_fetch=False))  # would say no
    router = await _router(mesh=conn, parser=parser)

    result = await router.run_turn(
        agent=_agent(), user_input="hi", mesh_query="explicit", mesh_topics=["telemetry"]
    )
    assert conn.calls == ["explicit"]  # explicit wins; parser not consulted for fetch
    assert result.parsed_intent is None


async def test_inferred_fetch_denied_by_policy_is_not_fatal():
    conn = RecordingConnector()
    # parser asks to fetch an out-of-scope topic; policy denies; turn still succeeds.
    parser = StubParser(ParsedIntent(needs_fetch=True, topics=["aero"]))
    router = await _router(mesh=conn, parser=parser, policy=PolicyEngine(enabled=True))

    result = await router.run_turn(agent=_agent(scope=("telemetry",)), user_input="aero data?")
    assert result.mesh_result is None  # denied, skipped
    assert result.response == "ok"  # turn completed


async def test_parse_span_emitted():
    from ezra_core.observability.tracer import EzraTracer

    tracer, exporter = EzraTracer.in_memory()
    conn = RecordingConnector()
    parser = StubParser(ParsedIntent(needs_fetch=True, topics=["telemetry"]))
    router = await _router(mesh=conn, parser=parser, tracer=tracer)
    await router.run_turn(agent=_agent(), user_input="latest?")
    assert "router.parse" in {s.name for s in exporter.get_finished_spans()}
