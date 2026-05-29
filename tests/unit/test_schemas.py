from datetime import datetime, timezone

from ezra_core.schemas import (
    AgentRegistration,
    Commitment,
    Contradiction,
    MeshResult,
    Provenance,
    SemanticFact,
    SessionGraph,
    SessionGraphState,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_session_graph_defaults():
    g = SessionGraph(session_graph_id="g1", created_at=_now())
    assert g.state is SessionGraphState.ACTIVE
    assert g.merge_strategy == "last_write_wins"
    assert g.active_agents == [] and g.terminated_agents == []
    assert g.belief_retention_days is None  # infinite by default


def test_agent_registration_scope():
    reg = AgentRegistration(
        agent_id="a", session_graph_id="g1", permission_scope=["telemetry"], spawned_at=_now()
    )
    assert reg.terminated_at is None
    assert reg.trust_scores == {}


def test_commitment_and_contradiction():
    c = Commitment(
        id="c1", session_graph_id="g1", agent_id="a", turn_index=0,
        type="fact", claim="stock is 2", topic="parts", created_at=_now(),
    )
    assert c.trust_score == 1.0 and c.superseded is False
    contra = Contradiction(
        existing_commitment_id="c1", existing_agent_id="a", new_input_claim="stock is 5",
        new_agent_id="b", topic="parts", similarity_score=0.91, nli_confidence=0.95,
        detected_at=_now(),
    )
    assert contra.nli_label == "contradiction"


def test_mesh_result_provenance_defaults():
    result = MeshResult(
        data={"stock": 2},
        provenance=Provenance(source="mongodb:parts", queried_at=_now()),
    )
    assert result.provenance.time_travel_available is False
    assert result.provenance.confidence == 1.0


def test_semantic_fact_confidence_bounds():
    fact = SemanticFact(
        id="s1", user_id="u", subject="x", predicate="is", object="y",
        confidence=0.8, created_at=_now(), updated_at=_now(),
    )
    assert fact.tier == "archival"
