"""Audit activity-feed: the store, the EzraService write points, and the REST read.

Covers the three layers with in-memory infra: ``InMemoryAuditLog`` ordering /
isolation / limit; that ``EzraService`` records the right events on commit,
contradiction+reconciliation, fetch, denial, revert, and rewind; and that
``GET /ezra/audit`` returns the feed.
"""

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from ezra_core.adk_service.service import EzraService
from ezra_core.api import create_app
from ezra_core.audit.store import InMemoryAuditLog
from ezra_core.belief.store import InMemoryBeliefStore
from ezra_core.mesh.base import BaseConnector
from ezra_core.policy.engine import PolicyEngine
from ezra_core.schemas.audit import AuditEvent
from ezra_core.schemas.belief import Commitment, Contradiction
from ezra_core.schemas.mesh import MeshResult, Provenance


# -- store ----------------------------------------------------------------- #
def _event(graph, etype, *, agent="a", ts=None):
    return AuditEvent(
        id=f"{graph}-{etype}-{ts}",
        session_graph_id=graph,
        agent_id=agent,
        event_type=etype,
        created_at=ts or datetime.now(timezone.utc),
    )


async def test_store_orders_oldest_first_and_isolates_by_graph():
    log = InMemoryAuditLog()
    base = datetime.now(timezone.utc)
    await log.append(_event("g1", "agent_spawned", ts=base + timedelta(seconds=2)))
    await log.append(_event("g1", "belief_committed", ts=base + timedelta(seconds=1)))
    await log.append(_event("g2", "agent_spawned", ts=base))

    g1 = await log.get_for_graph("g1")
    assert [e.event_type for e in g1] == ["belief_committed", "agent_spawned"]  # oldest first
    assert all(e.session_graph_id == "g1" for e in g1)


async def test_store_limit_keeps_most_recent():
    log = InMemoryAuditLog()
    base = datetime.now(timezone.utc)
    for i in range(5):
        await log.append(_event("g", "belief_committed", ts=base + timedelta(seconds=i)))
    out = await log.get_for_graph("g", limit=2)
    assert len(out) == 2
    # the two most recent, still oldest-first
    assert out[0].created_at < out[1].created_at


# -- EzraService write points --------------------------------------------- #
class StubChecker:
    """Flags a contradiction iff an active commitment on the topic differs."""

    def check(self, *, new_claim, new_topic, new_agent_id, commitments):
        for c in commitments:
            if c.topic == new_topic and c.claim != new_claim:
                return Contradiction(
                    existing_commitment_id=c.id,
                    existing_agent_id=c.agent_id,
                    new_input_claim=new_claim,
                    new_agent_id=new_agent_id,
                    topic=new_topic,
                    similarity_score=0.88,
                    nli_confidence=0.97,
                    detected_at=datetime.now(timezone.utc),
                )
        return None


class FakeConnector(BaseConnector):
    time_travel_available = True

    async def fetch(self, query, agent_id, permission_scope, as_of=None):
        return MeshResult(
            data=[{"x": 1}, {"x": 2}],
            provenance=Provenance(
                source="snowflake:T",
                time_travel_available=True,
                queried_at=datetime.now(timezone.utc),
            ),
        )


def _commit(claim, topic, agent="eng", turn=1):
    return Commitment(
        id=f"{agent}-{topic}-{turn}",
        session_graph_id="g",
        agent_id=agent,
        turn_index=turn,
        type="decision",
        claim=claim,
        topic=topic,
        created_at=datetime.now(timezone.utc),
    )


def _service(audit, **kw):
    return EzraService(
        session_graph_id="g",
        agent_id=kw.pop("agent_id", "strategist"),
        permission_scope=list(kw.pop("scope", ("tyres",))),
        belief_store=kw.pop("belief_store", InMemoryBeliefStore()),
        audit_log=audit,
        **kw,
    )


async def test_commit_records_committed_event():
    audit = InMemoryAuditLog()
    svc = _service(audit, checker=StubChecker())
    await svc.commit("run softs", "tyres", turn_index=1)
    events = await audit.get_for_graph("g")
    types = [e.event_type for e in events]
    assert "belief_committed" in types
    committed = next(e for e in events if e.event_type == "belief_committed")
    assert committed.topic == "tyres" and committed.detail["claim"] == "run softs"


async def test_commit_with_contradiction_records_detect_and_reconcile():
    beliefs = InMemoryBeliefStore()
    await beliefs.append(_commit("run softs", "tyres", agent="weather"))
    audit = InMemoryAuditLog()
    svc = _service(
        audit, belief_store=beliefs, checker=StubChecker(),
        merge_strategy="highest_trust", trust_for=lambda a, t: 0.6,
    )
    await svc.commit("run wets", "tyres", turn_index=2, trust_score=0.95)
    types = [e.event_type for e in await audit.get_for_graph("g")]
    assert "contradiction_detected" in types
    assert "contradiction_reconciled" in types
    detected = next(
        e for e in await audit.get_for_graph("g")
        if e.event_type == "contradiction_detected"
    )
    assert detected.detail["similarity"] == 0.88
    assert detected.detail["with_agent"] == "weather"


async def test_query_records_fetch_with_provenance():
    audit = InMemoryAuditLog()
    svc = _service(audit, scope=("tyres",), mesh=FakeConnector())
    await svc.query("recent stints", topics=["tyres"])
    fetch = next(e for e in await audit.get_for_graph("g") if e.event_type == "federated_fetch")
    assert fetch.detail["source"] == "snowflake:T"
    assert fetch.detail["rows"] == 2
    assert fetch.detail["time_travel_available"] is True


async def test_denied_fetch_records_denial_and_raises():
    from ezra_core.policy.engine import PolicyDeniedError

    audit = InMemoryAuditLog()
    svc = _service(audit, scope=("tyres",), mesh=FakeConnector(), policy=PolicyEngine(enabled=True))
    with pytest.raises(PolicyDeniedError):
        await svc.query("downforce?", topics=["aero"])
    denied = next(e for e in await audit.get_for_graph("g") if e.event_type == "fetch_denied")
    assert denied.topic == "aero"


async def test_rewind_records_event():
    beliefs = InMemoryBeliefStore()
    await beliefs.append(_commit("a", "tyres", turn=1))
    await beliefs.append(_commit("b", "tyres", turn=3))
    audit = InMemoryAuditLog()
    svc = _service(audit, belief_store=beliefs)
    await svc.rewind(2, reason="bad call")
    rewound = next(e for e in await audit.get_for_graph("g") if e.event_type == "belief_rewound")
    assert rewound.detail["rewound_to_turn"] == 2


# -- REST read ------------------------------------------------------------- #
def _http(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_audit_endpoint_returns_feed():
    audit = InMemoryAuditLog()
    await audit.append(_event("race-1", "agent_spawned"))
    await audit.append(_event("race-1", "belief_committed"))
    app = create_app(belief_store=InMemoryBeliefStore(), audit_log=audit, bearer_token="t")
    async with _http(app) as c:
        r = await c.get(
            "/ezra/audit", params={"session_graph_id": "race-1"},
            headers={"Authorization": "Bearer t"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["session_graph_id"] == "race-1"
        assert {e["event_type"] for e in body["events"]} == {
            "agent_spawned", "belief_committed",
        }
        # bearer is required
        unauth = await c.get("/ezra/audit", params={"session_graph_id": "race-1"})
        assert unauth.status_code == 401


async def test_health_reports_audit():
    app = create_app(belief_store=InMemoryBeliefStore(), audit_log=InMemoryAuditLog())
    async with _http(app) as c:
        assert (await c.get("/ezra/health")).json()["audit"] is True
