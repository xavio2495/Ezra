"""RemoteEzraService — the HTTP client that lets a remote ADK agent drive a
deployed Ezra. Tested against the real ASGI app via httpx ASGITransport (no
network), including that an EzraToolset wraps the remote service unchanged."""

import httpx

from ezra_core.adk_service.remote import RemoteEzraService
from ezra_core.adk_service.service import EzraService
from ezra_core.api import create_app
from ezra_core.belief.store import InMemoryBeliefStore

TOKEN = "secret"


class StubChecker:
    def check(self, **kwargs):
        return None


def _app(beliefs):
    def factory(graph_id, agent_id, scope):
        return EzraService(
            session_graph_id=graph_id,
            agent_id=agent_id,
            permission_scope=scope,
            belief_store=beliefs,
            checker=StubChecker(),
            merge_strategy="last_write_wins",
        )

    return create_app(belief_store=beliefs, service_factory=factory, bearer_token=TOKEN)


def _remote(app, beliefs):
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    return RemoteEzraService(
        "http://test", session_graph_id="g", agent_id="a",
        permission_scope=["tyres", "rain"], client=client,
    )


async def test_remote_commit_rewind_revert_roundtrip():
    beliefs = InMemoryBeliefStore()
    svc = _remote(_app(beliefs), beliefs)

    out = await svc.commit("softs", "tyres", turn_index=1)
    assert out.commitment.claim == "softs"
    await svc.commit("wets", "rain", turn_index=2)

    rewound = await svc.rewind(1, reason="reset")
    assert rewound.rewound_to_turn == 1
    snap = await svc.belief_snapshot()
    assert {c.claim for c in snap.commitments} == {"softs"}

    await svc.revert(out.commitment.id, reason="bad", turn_index=3)
    snap2 = await svc.belief_snapshot()
    assert snap2.commitments == []
    await svc.aclose()


async def test_remote_replay_is_time_aware():
    beliefs = InMemoryBeliefStore()
    svc = _remote(_app(beliefs), beliefs)
    await svc.commit("softs", "tyres", turn_index=1)
    await svc.commit("mediums", "tyres", turn_index=5)
    at1 = await svc.replay(1)
    assert {c.claim for c in at1.commitments} == {"softs"}  # before turn 5
    await svc.aclose()


async def test_toolset_wraps_remote_service_unchanged():
    import pytest

    pytest.importorskip("google.adk")
    from ezra_core.adk_service import EzraToolset

    beliefs = InMemoryBeliefStore()
    svc = _remote(_app(beliefs), beliefs)
    ts = EzraToolset(svc)
    tools = {t.name: t for t in await ts.get_tools()}
    # the rewind tool drives the REMOTE service over HTTP, identical to in-process.
    await tools["commit_belief"].func("softs", "tyres")
    await tools["commit_belief"].func("wets", "rain")
    out = await tools["rewind_beliefs"].func(turn=1, reason="reset")
    assert out["status"] == "success"
    await svc.aclose()
