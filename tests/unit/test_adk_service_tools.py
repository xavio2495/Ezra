"""Platform-owned ADK integration surface (``ezra_core.adk_service.adk``).

The tool functions are exercised directly (no Agent/Runner) over in-memory
stores + a stub checker. ``build_ezra_agent`` is tested for real when google-adk
is installed (the ``agents`` group), and skipped otherwise.
"""

from datetime import datetime, timezone

import pytest

from ezra_core.adk_service import (
    TurnCounter,
    adk_model_id,
    build_ezra_agent,
    ezra_adk_tools,
)
from ezra_core.adk_service.service import EzraService
from ezra_core.belief.store import InMemoryBeliefStore
from ezra_core.policy.engine import PolicyEngine
from ezra_core.schemas.belief import Commitment, Contradiction


class StubChecker:
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


def _commit(claim, topic, agent="weather", turn=1):
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


def _service(scope=("final_stint",), **kw):
    beliefs = kw.pop("belief_store", InMemoryBeliefStore())
    return (
        EzraService(
            session_graph_id="g",
            agent_id="strategist",
            permission_scope=list(scope),
            belief_store=beliefs,
            checker=StubChecker(),
            **kw,
        ),
        beliefs,
    )


_EXPECTED_TOOLS = [
    "recall", "belief_snapshot", "fetch_federated", "commit_belief",
    "revert_belief", "rewind_beliefs", "replay_beliefs", "branch_beliefs",
]


def test_ezra_adk_tools_returns_the_full_named_surface():
    svc, _ = _service()
    names = [f.__name__ for f in ezra_adk_tools(svc, turns=TurnCounter())]
    assert names == _EXPECTED_TOOLS


def test_ezra_adk_tools_accepts_turns_and_events_positionally():
    # The live demo path (agents.py) calls it as build_tools(service, turns, events)
    # with THREE positional args — keep that signature working.
    svc, _ = _service()
    events: list = []
    tools = ezra_adk_tools(svc, TurnCounter(), events)
    assert [f.__name__ for f in tools] == _EXPECTED_TOOLS


async def test_commit_belief_tool_detects_and_records_contradiction():
    beliefs = InMemoryBeliefStore()
    await beliefs.append(_commit("run softs", "final_stint", agent="weather"))
    trust = {("strategist", "final_stint"): 0.9, ("weather", "final_stint"): 0.6}
    svc, _ = _service(
        belief_store=beliefs,
        merge_strategy="highest_trust",
        trust_for=lambda a, t: trust.get((a, t), 0.6),
    )
    events: list = []
    tools = {f.__name__: f for f in ezra_adk_tools(svc, events=events)}

    result = await tools["commit_belief"]("run wets", "final_stint")
    assert result["status"] == "success"
    assert result["contradiction"]["with_agent"] == "weather"
    assert result["contradiction"]["decision"] == "accept_new"
    # the events sink captured the same contradiction for fleet-level reporting
    assert events and events[0]["kind"] == "contradiction"


async def test_fetch_federated_tool_denied_out_of_scope():
    svc, _ = _service(scope=("final_stint",), policy=PolicyEngine(enabled=True))
    tools = {f.__name__: f for f in ezra_adk_tools(svc)}
    result = await tools["fetch_federated"]("downforce target?", "aero")
    assert result["status"] == "denied"


def test_adk_model_id_strips_litellm_prefix():
    assert adk_model_id("gemini/gemini-2.5-flash") == "gemini-2.5-flash"
    assert adk_model_id("gemini-2.5-flash") == "gemini-2.5-flash"


def test_build_ezra_agent_registers_ezra_toolset():
    pytest.importorskip("google.adk")
    svc, _ = _service()
    agent, turns = build_ezra_agent(
        svc, name="strategist", model="gemini/gemini-2.5-flash",
        instruction="You strategise.",
    )
    assert agent.name == "strategist"
    assert isinstance(turns, TurnCounter)
    # the full Ezra tool surface is registered on the agent
    assert len(agent.tools) == len(_EXPECTED_TOOLS)
