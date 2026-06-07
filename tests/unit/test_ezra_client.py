"""Tests for the standalone ezra-client package.

Three layers: the vendored wire models stay field-compatible with the platform
schemas (drift guard); ``RemoteEzraService`` parses the REST responses into typed
models and maps 403 -> PolicyDeniedError; and the ADK tool functions drive the
service surface (commit + contradiction, fetch denial).
"""

from datetime import datetime, timezone

import httpx
import pytest

from ezra_client import PolicyDeniedError, RemoteEzraError, RemoteEzraService
from ezra_client import models as cm
from ezra_client.tools import ezra_adk_tools


# -- drift guard: vendored models match ezra_core schemas ------------------ #
def test_vendored_models_match_platform_schemas():
    from ezra_core.adk_service.service import CommitResult as CoreCommitResult
    from ezra_core.schemas import belief, branch, memory, mesh

    pairs = [
        (cm.Commitment, belief.Commitment),
        (cm.Contradiction, belief.Contradiction),
        (cm.Resolution, belief.Resolution),
        (cm.BeliefSnapshot, belief.BeliefSnapshot),
        (cm.RewindResult, belief.RewindResult),
        (cm.CommitResult, CoreCommitResult),
        (cm.WarmSummary, memory.WarmSummary),
        (cm.Provenance, mesh.Provenance),
        (cm.MeshResult, mesh.MeshResult),
        (cm.Branch, branch.Branch),
    ]
    for vendored, core in pairs:
        assert set(vendored.model_fields) == set(core.model_fields), (
            f"{vendored.__name__} drifted from {core.__module__}.{core.__name__}"
        )


# -- RemoteEzraService over a mock transport ------------------------------- #
def _commit_doc(agent="strategist", topic="tyres", claim="Start on softs.", turn=1):
    return {
        "id": f"{agent}-{topic}-{turn}",
        "session_graph_id": "g",
        "agent_id": agent,
        "turn_index": turn,
        "type": "decision",
        "claim": claim,
        "topic": topic,
        "trust_score": 0.8,
        "superseded": False,
        "superseded_by": None,
        "redacted": False,
        "redaction_reason": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/ezra/commit":
        return httpx.Response(
            200,
            json={
                "commitment": _commit_doc(),
                "contradiction": {
                    "existing_commitment_id": "tyre-tyres-1",
                    "existing_agent_id": "tyre_engineer",
                    "new_input_claim": "Start on softs.",
                    "new_agent_id": "strategist",
                    "topic": "tyres",
                    "similarity_score": 0.84,
                    "nli_label": "contradiction",
                    "nli_confidence": 0.97,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                },
                "resolution": {
                    "decision": "keep_existing",
                    "fallback_strategy": None,
                    "resolved_commitment_id": None,
                    "merge_strategy_used": "highest_trust",
                    "resolver_metadata": {},
                },
            },
        )
    if path == "/ezra/belief/snapshot":
        return httpx.Response(
            200,
            json={"session_graph_id": "g", "as_of_turn": None, "commitments": [_commit_doc()]},
        )
    if path == "/ezra/mesh/query":
        return httpx.Response(
            200,
            json={
                "data": [{"x": 1}, {"x": 2}],
                "provenance": {
                    "source": "snowflake:T",
                    "synced_at": None,
                    "field_types": {},
                    "confidence": 1.0,
                    "time_travel_available": True,
                    "queried_at": datetime.now(timezone.utc).isoformat(),
                },
                "topics": ["tyres"],
                "fetch_time_ms": 12.0,
            },
        )
    if path == "/ezra/recall":
        return httpx.Response(
            200,
            json=[{
                "id": "s1", "session_graph_id": "g", "agent_id": "strategist",
                "summary": "prior stint summary", "topics": ["tyres"],
                "salience": 1.0, "created_at": datetime.now(timezone.utc).isoformat(),
            }],
        )
    if path == "/ezra/rewind":
        return httpx.Response(
            200,
            json={"session_graph_id": "g", "rewound_to_turn": 2,
                  "marker_id": "m1", "superseded_ids": ["a"], "reactivated_ids": ["b"]},
        )
    if path == "/ezra/branch":
        return httpx.Response(
            200,
            json={"branch_id": "whatif", "parent_session_graph_id": "g",
                  "parent_turn": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                  "description": None, "mutations": [], "spawned_agents": [], "forward_runs": []},
        )
    if path == "/ezra/mesh/denied":  # not a real path; the denial test posts /mesh/query
        pass
    return httpx.Response(404, json={"detail": "not found"})


def _svc(handler=_handler, **kw):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://t")
    return RemoteEzraService(
        "http://t", session_graph_id="g", agent_id="strategist",
        permission_scope=["tyres", "strategy"], client=client, **kw,
    )


async def test_commit_parses_commit_result_with_contradiction():
    svc = _svc()
    out = await svc.commit("Start on softs.", "tyres", turn_index=1)
    assert isinstance(out, cm.CommitResult)
    assert out.commitment.claim == "Start on softs."
    assert out.contradiction.existing_agent_id == "tyre_engineer"
    assert out.resolution.decision == "keep_existing"
    await svc.aclose()


async def test_snapshot_query_recall_rewind_branch_parse():
    svc = _svc()
    snap = await svc.belief_snapshot()
    assert snap.commitments[0].topic == "tyres"
    mesh = await svc.query("recent stints", topics=["tyres"])
    assert mesh.provenance.source == "snowflake:T" and mesh.provenance.time_travel_available
    summaries = await svc.recall("stints")
    assert summaries[0].summary == "prior stint summary"
    rw = await svc.rewind(2, reason="bad call")
    assert rw.rewound_to_turn == 2 and rw.superseded_ids == ["a"]
    br = await svc.branch_from(1, "whatif")
    assert br.branch_id == "whatif"
    await svc.aclose()


async def test_403_maps_to_policy_denied():
    def deny(request):
        return httpx.Response(403, json={"detail": "topic 'aero' not in agent scope [...]"})

    svc = _svc(handler=deny)
    with pytest.raises(PolicyDeniedError) as ei:
        await svc.query("downforce?", topics=["aero"])
    assert ei.value.topic == "aero"
    await svc.aclose()


async def test_500_maps_to_remote_error():
    def boom(request):
        return httpx.Response(500, json={"detail": "kaboom"})

    svc = _svc(handler=boom)
    with pytest.raises(RemoteEzraError):
        await svc.belief_snapshot()
    await svc.aclose()


# -- ADK tool functions over the client ------------------------------------ #
async def test_tools_commit_belief_surfaces_contradiction():
    svc = _svc()
    tools = {f.__name__: f for f in ezra_adk_tools(svc)}
    assert set(tools) == {
        "recall", "belief_snapshot", "fetch_federated", "commit_belief",
        "revert_belief", "rewind_beliefs", "replay_beliefs", "branch_beliefs",
    }
    res = await tools["commit_belief"]("Start on softs.", "tyres")
    assert res["status"] == "success"
    assert res["contradiction"]["with_agent"] == "tyre_engineer"
    assert res["contradiction"]["similarity"] == 0.84
    await svc.aclose()


async def test_tools_fetch_denied_returns_denied_status():
    def deny(request):
        return httpx.Response(403, json={"detail": "topic 'aero' not in agent scope [...]"})

    svc = _svc(handler=deny)
    tools = {f.__name__: f for f in ezra_adk_tools(svc)}
    res = await tools["fetch_federated"]("downforce?", "aero")
    assert res["status"] == "denied"
    await svc.aclose()
