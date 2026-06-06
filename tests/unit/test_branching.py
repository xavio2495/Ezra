from datetime import datetime, timezone

from ezra_core.belief.branching import BranchManager, InMemoryBranchStore
from ezra_core.belief.replay import snapshot_now
from ezra_core.belief.store import InMemoryBeliefStore
from ezra_core.schemas.belief import Commitment
from ezra_core.session_graph import InMemorySessionGraphStore, SessionGraph


def _c(cid, *, turn, topic, claim, graph="race-1") -> Commitment:
    return Commitment(
        id=cid,
        session_graph_id=graph,
        agent_id="strategist",
        turn_index=turn,
        type="decision",
        claim=claim,
        topic=topic,
        created_at=datetime.now(timezone.utc),
    )


async def _setup():
    graphs = InMemorySessionGraphStore()
    beliefs = InMemoryBeliefStore()
    branches = InMemoryBranchStore()
    await SessionGraph.create(store=graphs, session_graph_id="race-1", merge_strategy="highest_trust")
    await beliefs.append(_c("t1", turn=1, topic="tyres", claim="start on softs"))
    await beliefs.append(_c("f1", turn=3, topic="fuel", claim="fuel margin ok"))
    await beliefs.append(_c("t2", turn=10, topic="tyres", claim="switch to hards late"))
    mgr = BranchManager(graph_store=graphs, belief_store=beliefs, branch_store=branches)
    return mgr, beliefs, graphs


async def test_branch_from_seeds_state_as_of_turn():
    mgr, beliefs, graphs = await _setup()
    branch = await mgr.branch_from(session_graph_id="race-1", turn=3, branch_id="early")

    assert branch.parent_session_graph_id == "race-1"
    assert branch.parent_turn == 3
    # Branch graph exists and inherited the parent's merge strategy.
    assert (await graphs.get("early")).merge_strategy == "highest_trust"
    # As-of turn 3: t1 + f1 seeded, the turn-10 commitment is NOT.
    seeded = await snapshot_now(beliefs, "early")
    assert {c.claim for c in seeded.commitments} == {"start on softs", "fuel margin ok"}


async def test_mutate_belief_records_and_appends():
    mgr, beliefs, _ = await _setup()
    await mgr.branch_from(session_graph_id="race-1", turn=3, branch_id="early")

    c = await mgr.mutate_belief(
        branch_id="early", agent_id="rival_strat", new_claim="pit now for hards", topic="tyres"
    )
    assert c.session_graph_id == "early"
    assert c.turn_index == 4  # parent_turn + 1
    snap = await snapshot_now(beliefs, "early")
    assert "pit now for hards" in {x.claim for x in snap.commitments}


async def test_run_forward_invokes_step_per_turn():
    mgr, beliefs, _ = await _setup()
    await mgr.branch_from(session_graph_id="race-1", turn=3, branch_id="early")

    async def step(*, branch_id, turn):
        await beliefs.append(
            _c(f"fwd-{turn}", turn=turn, topic="tyres", claim=f"turn {turn} call", graph=branch_id)
        )
        return f"ran turn {turn}"

    results = await mgr.run_forward(branch_id="early", until_turn=6, step=step)
    assert results == ["ran turn 4", "ran turn 5", "ran turn 6"]
    snap = await snapshot_now(beliefs, "early")
    assert {"turn 4 call", "turn 5 call", "turn 6 call"} <= {c.claim for c in snap.commitments}


async def test_spawn_agent_registers_on_branch_graph():
    mgr, beliefs, graphs = await _setup()
    await mgr.branch_from(session_graph_id="race-1", turn=3, branch_id="early")

    reg = await mgr.spawn_agent(
        branch_id="early",
        agent_id="rival_strat",
        permission_scope=["tyres", "telemetry"],
        role="rival strategist",
    )
    assert reg.session_graph_id == "early"
    assert reg.permission_scope == ["tyres", "telemetry"]

    # Registered on the branch's own session-graph record (not the parent's).
    branch_graph = await graphs.get("early")
    assert [a.agent_id for a in branch_graph.active_agents] == ["rival_strat"]
    parent_graph = await graphs.get("race-1")
    assert "rival_strat" not in {a.agent_id for a in parent_graph.active_agents}

    # The counterfactual agent can then commit and drive the branch forward.
    c = await mgr.mutate_belief(
        branch_id="early", agent_id="rival_strat", new_claim="box now", topic="tyres"
    )
    assert c.agent_id == "rival_strat"


async def test_spawn_agent_at_turn_and_duplicate_guard():
    mgr, *_ = await _setup()
    await mgr.branch_from(session_graph_id="race-1", turn=3, branch_id="early")

    await mgr.spawn_agent(
        branch_id="early", agent_id="db_specialist", permission_scope=["telemetry"], at_turn=15
    )
    # Duplicate agent_id is rejected.
    import pytest

    with pytest.raises(ValueError):
        await mgr.spawn_agent(
            branch_id="early", agent_id="db_specialist", permission_scope=["telemetry"]
        )


async def test_spawn_agent_unknown_branch_raises():
    mgr, *_ = await _setup()
    import pytest

    with pytest.raises(KeyError):
        await mgr.spawn_agent(
            branch_id="nope", agent_id="x", permission_scope=["tyres"]
        )


async def test_diff_branches_shows_divergence():
    mgr, beliefs, _ = await _setup()
    await mgr.branch_from(session_graph_id="race-1", turn=3, branch_id="early")
    await mgr.mutate_belief(
        branch_id="early", agent_id="rival", new_claim="undercut on lap 18", topic="tyres"
    )

    diff = await mgr.diff_branches(original="race-1", branch="early", from_turn=1)
    tyres = next(d for d in diff.diverged_commitments if d["topic"] == "tyres")
    assert "undercut on lap 18" in tyres["only_in_branch"]
    # The parent's later turn-10 tyre call never entered the branch.
    assert "switch to hards late" in tyres["only_in_original"]
