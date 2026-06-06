"""Each SDK example runs end-to-end against the offline harness and produces the
documented result. This guards the examples/ surface against SDK drift — if a
public method changes shape, an example (and this test) breaks."""

from examples import (
    basic_chat,
    branching_replay,
    cross_graph_inheritance,
    custom_reconciler,
    multi_agent_session_graph,
    replay_session,
    with_mongodb_source,
    with_snowflake_source,
)
from examples._harness import build_offline_ezra


async def _run(mod):
    ezra = build_offline_ezra()
    try:
        return await mod.run(ezra)
    finally:
        await ezra.aclose()


async def test_basic_chat_runs_a_full_turn():
    r = await _run(basic_chat)
    assert r["response"]
    assert r["context_slots"] > 0
    assert r["learning_ran"] is True


async def test_multi_agent_beliefs_are_scope_filtered():
    r = await _run(multi_agent_session_graph)
    assert r["agents"] == ["strategist", "tyre_engineer"]
    assert r["engineer_sees"] == ["tyres"]  # cannot see the 'strategy' belief
    assert set(r["strategist_sees"]) == {"strategy", "tyres"}


async def test_mongodb_source_no_time_travel():
    r = await _run(with_mongodb_source)
    assert r["source"].startswith("mongodb:")
    assert r["time_travel_available"] is False
    assert r["rows"] == 2


async def test_snowflake_source_has_time_travel():
    r = await _run(with_snowflake_source)
    assert r["source"] == "snowflake:EZRA.PUBLIC.RACE_RESULTS"
    assert r["time_travel_available"] is True
    assert "AT (TIMESTAMP" in r["time_travel_sql"]
    assert r["rows"] == 2 and r["historical_rows"] == 2


async def test_custom_reconciler_escalates_on_three_way_conflict():
    r = await _run(custom_reconciler)
    assert r["second_decision"] == "keep_existing"  # highest_trust fallback
    assert r["third_decision"] == "escalate"  # custom policy fired
    assert r["third_strategy"] == "custom"


async def test_branching_replay_diff_shows_divergence():
    r = await _run(branching_replay)
    assert r["branch_id"] == "what-if-wets"
    tyres = next(d for d in r["diverged"] if d["topic"] == "tyres")
    assert "Switch to wets at lap 43" in tyres["only_in_branch"]
    assert "Confirm: stay on softs to the end" in tyres["only_in_original"]


async def test_cross_graph_inheritance_loads_prior_core_memory():
    r = await _run(cross_graph_inheritance)
    assert r["inherited_facts"] == ["near-impossible; track position is decisive"]
    assert r["own_facts"] == []  # belief/core history starts clean for the new graph


async def test_replay_session_is_time_aware():
    r = await _run(replay_session)
    assert r["at_turn_3"] == ["Start on softs"]  # original plan still active at t3
    assert r["now"] == ["Revised: switch to mediums"]  # superseded by the revision


async def test_intent_fetch_parses_translates_and_fetches():
    from examples import intent_fetch

    r = await _run(intent_fetch)
    assert r["needs_fetch"] is True
    # the connector composed a constrained pushdown query (not SELECT *)
    assert "WHERE circuit = 'Monaco'" in r["translated_sql"]
    assert "SELECT season, winner" in r["translated_sql"]
    assert r["rows"] == 2


async def test_adk_service_runner_registers_and_drives_the_full_surface():
    import pytest

    pytest.importorskip("google.adk")
    from examples import adk_service_runner

    r = await _run(adk_service_runner)
    assert r["runner_has_memory_service"] is True
    assert "rewind_beliefs" in r["tool_names"] and "revert_belief" in r["tool_names"]
    # rewind to turn 1 undoes the turn-2 (strategy) commit; revert then drops the opener.
    assert r["before_rewind"] == ["plan a one-stop", "start on softs"]
    assert r["after_rewind"] == ["start on softs"]
    assert r["after_revert"] == []
    assert r["revert_status"] == "success"
