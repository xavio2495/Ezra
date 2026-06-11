"""Demo Conductor (demo/conductor): start/prompt/ops endpoints + the SSE stream.

Runs entirely offline over ``build_offline_ezra`` — the conductor's offline turn
path drives the REAL belief store / two-pass-stand-in checker / reconciler /
audit feed; only the LLM is the deterministic stand-in. The presenter-induced
contradiction (race_strategy softs → tyre_engineer hards) must detect, reconcile
via highest_trust, and land in the audit feed the dashboard derives from.
"""

import asyncio

import httpx
import pytest

from demo.conductor.app import CONDUCTOR_GRAPH, create_app
from demo.f1_race_weekend.adk_runtime.fleet import FLEET_PROMPTS


@pytest.fixture
def app():
    return create_app()


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://conductor"
    )


async def _audit(app) -> list[dict]:
    return await app.state.conductor.audit_snapshot()


async def test_start_spawns_fleet_and_audits_it(app):
    async with _client(app) as client:
        res = await client.post("/demo/start")
        assert res.status_code == 200
        body = res.json()
        assert body["graph_id"] == CONDUCTOR_GRAPH
        assert body["mode"] == "offline"
        assert len(body["agents"]) == 6

        # Idempotent: a second start returns the same fleet, no respawn.
        again = await client.post("/demo/start")
        assert again.json()["graph_id"] == CONDUCTOR_GRAPH

    events = await _audit(app)
    spawned = [e for e in events if e["event_type"] == "agent_spawned"]
    assert {e["agent_id"] for e in spawned} == {
        "race_strategy", "tyre_engineer", "aero_rd",
        "logistics", "telemetry_analyst", "weather_model",
    }


async def test_presenter_induced_contradiction_reconciles(app):
    async with _client(app) as client:
        await client.post("/demo/start")
        # The on-stage order: lower-trust race_strategy commits softs FIRST...
        first = await client.post(
            "/demo/agent/race_strategy/prompt", json={"text": FLEET_PROMPTS["race_strategy"]}
        )
        assert first.json()["committed"] == {"topic": "tyres", "claim": "Final stint: softs."}
        # ...then higher-trust tyre_engineer commits hards → accept_new supersedes.
        second = await client.post(
            "/demo/agent/tyre_engineer/prompt", json={"text": FLEET_PROMPTS["tyre_engineer"]}
        )
        assert second.json()["committed"] == {"topic": "tyres", "claim": "Final stint: hards."}

    events = await _audit(app)
    kinds = [e["event_type"] for e in events]
    assert "contradiction_detected" in kinds
    assert "contradiction_reconciled" in kinds

    active = await app.state.conductor.ezra.belief_store.get_active(
        CONDUCTOR_GRAPH, topic="tyres"
    )
    assert [c.claim for c in active] == ["Final stint: hards."]


async def test_unknown_agent_404_and_out_of_scope_commit_denied(app):
    async with _client(app) as client:
        await client.post("/demo/start")
        missing = await client.post("/demo/agent/nope/prompt", json={"text": "hi"})
        assert missing.status_code == 404
        # logistics holds parts/supplier/calendar — an 'aero' commit is refused
        # by the policy engine (scoping beat), not silently applied.
        denied = await client.post(
            "/demo/agent/logistics/prompt",
            json={"text": "Commit one belief on topic 'aero'."},
        )
        assert "DENIED" in denied.json()["text"]

    events = await _audit(app)
    assert not any(
        e["event_type"] == "belief_committed" and e["agent_id"] == "logistics"
        for e in events
    )


async def test_revert_rewind_and_branch_ops(app):
    async with _client(app) as client:
        await client.post("/demo/start")
        await client.post(
            "/demo/agent/weather_model/prompt", json={"text": FLEET_PROMPTS["weather_model"]}
        )

        reverted = await client.post("/demo/revert")
        assert reverted.status_code == 200
        assert reverted.json()["reverted"]

        rewound = await client.post("/demo/rewind", json={"turn": 1, "reason": "demo beat"})
        assert rewound.status_code == 200

        branched = await client.post("/demo/branch")
        assert branched.status_code == 200
        body = branched.json()
        assert body["branch_id"].startswith(f"{CONDUCTOR_GRAPH}-whatif")

    events = await _audit(app)
    kinds = [e["event_type"] for e in events]
    assert "belief_reverted" in kinds
    assert "belief_rewound" in kinds


async def test_stream_replays_audit_feed_as_sse(app):
    async with _client(app) as client:
        await client.post("/demo/start")

    # The SSE body is an unbounded generator; httpx's in-process ASGITransport
    # buffers an infinite response and never yields, so drive the real generator
    # directly and stop once the spawned fleet has replayed as `audit` frames.
    conductor = app.state.conductor
    frames: list[str] = []
    stream = conductor.event_stream()
    try:
        while True:
            chunk = await asyncio.wait_for(stream.__anext__(), timeout=5)
            frames.append(chunk)
            if "event: audit" in chunk and "agent_spawned" in chunk:
                break
    finally:
        await stream.aclose()

    joined = "".join(frames)
    assert joined.startswith(": connected")
    assert "event: audit" in joined and "agent_spawned" in joined
