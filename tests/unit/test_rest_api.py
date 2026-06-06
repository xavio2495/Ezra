from datetime import datetime, timezone

import httpx
import pytest

from ezra_core.api import create_app
from ezra_core.belief.branching import BranchManager, InMemoryBranchStore
from ezra_core.belief.store import InMemoryBeliefStore
from ezra_core.mesh.snowflake import SnowflakeConnector
from ezra_core.policy.engine import PolicyEngine
from ezra_core.schemas.belief import Commitment
from ezra_core.session_graph import InMemorySessionGraphStore

TOKEN = "secret-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class StubChecker:
    def __init__(self, result=None):
        self.result = result

    def check(self, **kwargs):
        return self.result


def _commit(claim, topic, turn=1):
    return Commitment(
        id=f"{topic}-{claim[:4]}-{turn}",
        session_graph_id="race-1",
        agent_id="eng",
        turn_index=turn,
        type="decision",
        claim=claim,
        topic=topic,
        created_at=datetime.now(timezone.utc),
    )


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def client():
    beliefs = InMemoryBeliefStore()
    await beliefs.append(_commit("start softs", "tyres"))
    await beliefs.append(_commit("fuel tight", "fuel"))
    mgr = BranchManager(
        graph_store=InMemorySessionGraphStore(),
        belief_store=beliefs,
        branch_store=InMemoryBranchStore(),
    )
    app = create_app(
        belief_store=beliefs, checker=StubChecker(), branch_manager=mgr, bearer_token=TOKEN
    )
    async with _client(app) as c:
        yield c


async def test_health_needs_no_auth(client):
    r = await client.get("/ezra/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_snapshot_requires_bearer(client):
    r = await client.post("/ezra/belief/snapshot", json={"session_graph_id": "race-1"})
    assert r.status_code == 401


async def test_snapshot_scope_filtered(client):
    r = await client.post(
        "/ezra/belief/snapshot",
        headers=AUTH,
        json={"session_graph_id": "race-1", "scope": ["tyres"]},
    )
    assert r.status_code == 200
    assert {c["claim"] for c in r.json()["commitments"]} == {"start softs"}


async def test_belief_check_null_when_consistent(client):
    r = await client.post(
        "/ezra/belief/check",
        headers=AUTH,
        json={"session_graph_id": "race-1", "agent_id": "a", "claim": "x", "topic": "tyres"},
    )
    assert r.status_code == 200
    assert r.json()["contradiction"] is None


async def test_branch_then_diff(client):
    b = await client.post(
        "/ezra/branch",
        headers=AUTH,
        json={"session_graph_id": "race-1", "turn": 5, "branch_id": "wi"},
    )
    assert b.status_code == 200
    d = await client.post(
        "/ezra/branch/diff",
        headers=AUTH,
        json={"original": "race-1", "branch": "wi", "from_turn": 1},
    )
    assert d.status_code == 200
    assert d.json()["branch_id"] == "wi"


async def test_context_assemble_returns_scope_filtered_context():
    from fakeredis import aioredis

    from ezra_core.router import Router
    from ezra_core.tiers.hot import HotTier

    beliefs = InMemoryBeliefStore()
    await beliefs.append(_commit("start softs", "tyres"))
    await beliefs.append(_commit("fuel tight", "fuel"))
    router = Router(
        hot=HotTier(aioredis.FakeRedis(decode_responses=True)),
        belief_store=beliefs,
        llm=None,  # assemble never calls the model
    )
    app = create_app(belief_store=beliefs, router=router, bearer_token=TOKEN)
    async with _client(app) as c:
        r = await c.post(
            "/ezra/context/assemble",
            headers=AUTH,
            json={
                "session_graph_id": "race-1",
                "agent_id": "strategist",
                "scope": ["tyres"],
                "user_input": "what's the plan?",
                "system_prompt": "You strategise.",
            },
        )
    assert r.status_code == 200
    contents = " ".join(s["content"] for s in r.json()["slots"])
    assert "start softs" in contents
    assert "fuel tight" not in contents  # out-of-scope belief filtered out


async def test_context_assemble_400_without_router(client):
    r = await client.post(
        "/ezra/context/assemble",
        headers=AUTH,
        json={"session_graph_id": "race-1", "agent_id": "a", "user_input": "hi"},
    )
    assert r.status_code == 400


async def test_run_forward_501_without_step(client):
    await client.post(
        "/ezra/branch",
        headers=AUTH,
        json={"session_graph_id": "race-1", "turn": 5, "branch_id": "wi"},
    )
    r = await client.post(
        "/ezra/branch/run-forward",
        headers=AUTH,
        json={"branch_id": "wi", "until_turn": 7},
    )
    assert r.status_code == 501


async def test_run_forward_with_step_executes_turns():
    beliefs = InMemoryBeliefStore()
    await beliefs.append(_commit("start softs", "tyres"))
    mgr = BranchManager(
        graph_store=InMemorySessionGraphStore(),
        belief_store=beliefs,
        branch_store=InMemoryBranchStore(),
    )
    calls: list = []

    async def step(*, branch_id, turn):
        calls.append((branch_id, turn))
        return "ran"

    app = create_app(
        belief_store=beliefs, branch_manager=mgr, forward_step=step, bearer_token=TOKEN
    )
    async with _client(app) as c:
        await c.post(
            "/ezra/branch",
            headers=AUTH,
            json={"session_graph_id": "race-1", "turn": 5, "branch_id": "wi"},
        )
        r = await c.post(
            "/ezra/branch/run-forward",
            headers=AUTH,
            json={"branch_id": "wi", "until_turn": 7},
        )
    assert r.status_code == 200
    assert r.json()["steps"] == 2  # turns 6 and 7
    assert calls == [("wi", 6), ("wi", 7)]


def _app_with_service(beliefs, *, policy=None):
    """An app whose service_factory builds an EzraService over shared in-memory
    stores, so commit/recall/rewind/revert exercise the real service logic."""
    from ezra_core.adk_service.service import EzraService

    def factory(graph_id, agent_id, scope):
        return EzraService(
            session_graph_id=graph_id,
            agent_id=agent_id,
            permission_scope=scope,
            belief_store=beliefs,
            checker=StubChecker(),
            policy=policy,
            merge_strategy="last_write_wins",
        )

    return create_app(
        belief_store=beliefs, service_factory=factory, policy=policy, bearer_token=TOKEN
    )


async def test_commit_then_rewind_then_revert_over_rest():
    beliefs = InMemoryBeliefStore()
    app = _app_with_service(beliefs)
    async with _client(app) as c:
        base = {"session_graph_id": "g", "agent_id": "a", "scope": ["tyres"]}
        r1 = await c.post(
            "/ezra/commit", headers=AUTH,
            json={**base, "claim": "softs", "topic": "tyres", "turn_index": 1},
        )
        assert r1.status_code == 200
        cid = r1.json()["commitment"]["id"]
        await c.post(
            "/ezra/commit", headers=AUTH,
            json={**base, "claim": "wets", "topic": "rain", "turn_index": 2},
        )

        # rewind to turn 1 undoes the turn-2 commit.
        rw = await c.post("/ezra/rewind", headers=AUTH, json={**base, "turn": 1, "reason": "x"})
        assert rw.status_code == 200
        assert rw.json()["rewound_to_turn"] == 1

        snap = await c.post(
            "/ezra/belief/snapshot", headers=AUTH, json={"session_graph_id": "g"}
        )
        assert {x["claim"] for x in snap.json()["commitments"]} == {"softs"}

        # revert the surviving commitment.
        rv = await c.post(
            "/ezra/revert", headers=AUTH,
            json={**base, "commitment_id": cid, "reason": "bad", "turn_index": 3},
        )
        assert rv.status_code == 200
        snap2 = await c.post(
            "/ezra/belief/snapshot", headers=AUTH, json={"session_graph_id": "g"}
        )
        assert snap2.json()["commitments"] == []


async def test_recall_returns_empty_without_warm():
    beliefs = InMemoryBeliefStore()
    app = _app_with_service(beliefs)
    async with _client(app) as c:
        r = await c.post(
            "/ezra/recall", headers=AUTH,
            json={"session_graph_id": "g", "agent_id": "a", "scope": ["tyres"], "query": "x"},
        )
    assert r.status_code == 200 and r.json() == []


async def test_full_surface_endpoints_400_without_factory(client):
    r = await client.post(
        "/ezra/commit", headers=AUTH,
        json={"session_graph_id": "g", "agent_id": "a", "claim": "x",
              "topic": "t", "turn_index": 1},
    )
    assert r.status_code == 400


async def test_mesh_query_policy_denied():
    app = create_app(
        belief_store=InMemoryBeliefStore(),
        mesh=SnowflakeConnector("wh.x", executor=lambda sql: []),
        policy=PolicyEngine(enabled=True),
        bearer_token=TOKEN,
    )
    async with _client(app) as c:
        r = await c.post(
            "/ezra/mesh/query",
            headers=AUTH,
            json={
                "session_graph_id": "race-1",
                "agent_id": "a",
                "query": "contracts",
                "scope": ["tyres"],
                "topics": ["procurement"],
            },
        )
    assert r.status_code == 403
