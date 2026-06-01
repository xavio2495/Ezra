from datetime import datetime, timezone

import pytest

from ezra_core.adk_service import EzraService
from ezra_core.belief.branching import BranchManager, InMemoryBranchStore
from ezra_core.belief.store import InMemoryBeliefStore
from ezra_core.policy.engine import PolicyDeniedError, PolicyEngine
from ezra_core.schemas.belief import Commitment, Contradiction
from ezra_core.session_graph import InMemorySessionGraphStore


class StubChecker:
    def __init__(self, result=None):
        self.result = result

    def check(self, **kwargs):
        return self.result


def _commit(claim, topic):
    return Commitment(
        id=f"{topic}-{claim[:4]}",
        session_graph_id="race-1",
        agent_id="eng",
        turn_index=1,
        type="decision",
        claim=claim,
        topic=topic,
        created_at=datetime.now(timezone.utc),
    )


def _service(**overrides):
    beliefs = overrides.pop("belief_store", InMemoryBeliefStore())
    svc = EzraService(
        session_graph_id="race-1",
        agent_id="strategist",
        permission_scope=["tyres"],
        belief_store=beliefs,
        **overrides,
    )
    return svc, beliefs


async def test_belief_snapshot_is_scope_filtered():
    svc, beliefs = _service()
    await beliefs.append(_commit("start softs", "tyres"))
    await beliefs.append(_commit("fuel tight", "fuel"))
    snap = await svc.belief_snapshot()
    assert {c.claim for c in snap.commitments} == {"start softs"}


async def test_write_back_then_visible():
    svc, beliefs = _service()
    await svc.write_back("box on lap 18", "tyres", turn_index=2)
    snap = await svc.belief_snapshot()
    assert "box on lap 18" in {c.claim for c in snap.commitments}


async def test_belief_check_delegates_to_checker():
    contradiction = Contradiction(
        existing_commitment_id="c1",
        existing_agent_id="eng",
        new_input_claim="go long",
        new_agent_id="strategist",
        topic="tyres",
        similarity_score=0.9,
        nli_confidence=0.88,
        detected_at=datetime.now(timezone.utc),
    )
    svc, _ = _service(checker=StubChecker(contradiction))
    assert await svc.belief_check("go long", "tyres") is contradiction


async def test_policy_blocks_out_of_scope_write():
    svc, _ = _service(policy=PolicyEngine(enabled=True))
    with pytest.raises(PolicyDeniedError):
        await svc.write_back("buy fuel", "fuel", turn_index=2)  # 'fuel' not in scope


async def test_branch_from_via_service():
    beliefs = InMemoryBeliefStore()
    await beliefs.append(_commit("start softs", "tyres"))
    graphs = InMemorySessionGraphStore()
    branches = InMemoryBranchStore()
    mgr = BranchManager(graph_store=graphs, belief_store=beliefs, branch_store=branches)
    svc, _ = _service(belief_store=beliefs, branch_manager=mgr)

    branch = await svc.branch_from(5, "what-if")
    assert branch.parent_session_graph_id == "race-1"
    assert branch.parent_turn == 5
