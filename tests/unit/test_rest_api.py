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
