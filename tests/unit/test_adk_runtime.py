"""Deterministic tests for the Phase-2 pieces that don't need a live LLM.

Two layers are covered here with in-memory stores + a stub checker:

  * ``EzraService.commit`` — the detect → reconcile → write_back → supersede flow
    that the ADK ``commit_belief`` tool routes through.
  * the bound ADK tool functions (``build_tools``) — plain async functions, so
    they're exercised directly without an ``Agent``/``Runner``.

The full orchestrator (real ADK ``Runner`` + real Gemini) is a live smoke run
manually, not part of this suite.
"""

from datetime import datetime, timezone

from ezra_core.adk_service.service import EzraService
from ezra_core.belief.store import InMemoryBeliefStore
from ezra_core.policy.engine import PolicyEngine
from ezra_core.schemas.belief import Commitment, Contradiction
from demo.f1_race_weekend.adk_runtime.ezra_tools import TurnCounter, build_tools


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
                    similarity_score=0.9,
                    nli_confidence=0.9,
                    detected_at=datetime.now(timezone.utc),
                )
        return None


def _commit(claim, topic, agent="tyre", turn=1):
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


def _service(agent_id="strategist", scope=("final_stint",), **kw):
    beliefs = kw.pop("belief_store", InMemoryBeliefStore())
    svc = EzraService(
        session_graph_id="g",
        agent_id=agent_id,
        permission_scope=list(scope),
        belief_store=beliefs,
        checker=StubChecker(),
        **kw,
    )
    return svc, beliefs


# -- EzraService.commit ---------------------------------------------------- #
async def test_commit_without_conflict_just_writes():
    svc, beliefs = _service()
    out = await svc.commit("run softs", "final_stint", turn_index=1)
    assert out.contradiction is None and out.resolution is None
    active = await beliefs.get_active("g")
    assert [c.claim for c in active] == ["run softs"]


async def test_commit_highest_trust_new_wins_supersedes_old():
    beliefs = InMemoryBeliefStore()
    await beliefs.append(_commit("run softs", "final_stint", agent="weather"))
    svc, _ = _service(
        belief_store=beliefs,
        merge_strategy="highest_trust",
        trust_for=lambda a, t: 0.6,  # the existing 'weather' commit is low-trust
    )
    out = await svc.commit("run wets", "final_stint", turn_index=2, trust_score=0.95)
    assert out.contradiction is not None
    assert out.resolution.decision == "accept_new"
    active = {c.claim for c in await beliefs.get_active("g")}
    assert active == {"run wets"}  # old softs commit superseded


async def test_commit_highest_trust_existing_wins_keeps_both_records():
    beliefs = InMemoryBeliefStore()
    await beliefs.append(_commit("run softs", "final_stint", agent="tyre"))
    svc, _ = _service(
        belief_store=beliefs,
        merge_strategy="highest_trust",
        trust_for=lambda a, t: 0.95,  # existing 'tyre' commit is high-trust
    )
    out = await svc.commit("run wets", "final_stint", turn_index=2, trust_score=0.50)
    assert out.resolution.decision == "keep_existing"
    # New claim is still appended (audit), but the old one is NOT superseded.
    active = {c.claim for c in await beliefs.get_active("g")}
    assert active == {"run softs", "run wets"}


async def test_commit_blocked_out_of_scope():
    import pytest

    from ezra_core.policy.engine import PolicyDeniedError

    svc, _ = _service(scope=("final_stint",), policy=PolicyEngine(enabled=True))
    with pytest.raises(PolicyDeniedError):
        await svc.commit("buy fuel", "fuel", turn_index=1)


# -- bound ADK tools ------------------------------------------------------- #
async def test_commit_belief_tool_reports_contradiction():
    beliefs = InMemoryBeliefStore()
    await beliefs.append(_commit("run softs", "final_stint", agent="weather"))
    svc, _ = _service(
        belief_store=beliefs, merge_strategy="highest_trust", trust_for=lambda a, t: 0.6
    )
    tools = {f.__name__: f for f in build_tools(svc, TurnCounter())}

    result = await tools["commit_belief"]("run wets", "final_stint")
    assert result["status"] == "success"
    assert result["contradiction"]["with_agent"] == "weather"
    assert result["contradiction"]["decision"] == "accept_new"


async def test_fetch_federated_tool_denied_out_of_scope():
    svc, _ = _service(scope=("final_stint",), policy=PolicyEngine(enabled=True))
    tools = {f.__name__: f for f in build_tools(svc, TurnCounter())}
    result = await tools["fetch_federated"]("downforce target?", "aero")
    assert result["status"] == "denied"


async def test_belief_snapshot_tool_lists_active():
    beliefs = InMemoryBeliefStore()
    await beliefs.append(_commit("run softs", "final_stint"))
    svc, _ = _service(belief_store=beliefs)
    tools = {f.__name__: f for f in build_tools(svc, TurnCounter())}
    result = await tools["belief_snapshot"]()
    assert result["beliefs"][0]["claim"] == "run softs"
