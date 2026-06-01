from fakeredis import aioredis

from demo.f1_race_weekend.agents.roles import (
    always_on_roles,
    build_system_prompt,
    conditional_roles,
    role_by_id,
    roles_for_event,
)
from demo.f1_race_weekend.data_ingestion import build_dataset
from demo.f1_race_weekend.race_weekend_demo import run_demo
from demo.f1_race_weekend.spawning import SpawnController
from demo.f1_race_weekend.synthesised.data import parts_inventory
from ezra_core.session_graph import InMemorySessionGraphStore, SessionGraph
from ezra_core.tiers.hot import HotTier


def test_role_registry_shape():
    assert len(always_on_roles()) == 4
    # logistics scope excludes aero — the permission-denial beat must be real.
    assert "aero" not in role_by_id("logistics").permission_scope
    assert {r.agent_id for r in roles_for_event("fp1_start")} == {
        "telemetry_analyst",
        "weather_model",
    }
    assert role_by_id("parts_shortage").spawn_event == "inventory_drop"


def test_build_system_prompt_fills_template():
    prompt = build_system_prompt(role_by_id("tyre_engineer"))
    assert "Tyre Engineer" in prompt
    assert "tyres" in prompt
    assert "Team Ezra" in prompt


def test_synthesised_front_wing_is_short():
    fw = next(p for p in parts_inventory() if p["part_id"] == "FW-07")
    assert fw["stock"] < fw["race_requirement"]  # drives the shortage beat


def test_build_dataset_has_all_collections():
    data = build_dataset()
    assert set(data) >= {"parts_inventory", "rd_experiments", "supplier_contracts", "race_results"}


async def test_spawn_controller_dynamic_membership():
    store = InMemorySessionGraphStore()
    graph = await SessionGraph.create(store=store, session_graph_id="race-1")
    spawner = SpawnController(graph)

    await spawner.spawn_always_on()
    assert len(graph.active_agents) == 4

    await spawner.handle_event("fp1_start")
    assert len(graph.active_agents) == 6

    # Idempotent — re-firing the event spawns nobody new.
    await spawner.handle_event("fp1_start")
    assert len(graph.active_agents) == 6

    await spawner.terminate("weather_model")
    assert "weather_model" not in spawner.active_ids


async def test_run_demo_executes_all_six_beats():
    hot = HotTier(aioredis.FakeRedis(decode_responses=True), max_turns=8)
    result = await run_demo(hot=hot, scaling_counts=(1, 2))

    beat_names = [b.name for b in result.beats]
    assert beat_names == [
        "federation_and_dynamic_spawn",
        "permission_denial",
        "conditional_spawn_and_contradiction",
        "multi_agent_custom_resolver",
        "branching_replay",
        "scaling_proof",
    ]
    assert result.peak_agents == 7

    denial = result.beats[1].details
    assert denial["denied_topic"] == "aero"

    contradiction = result.beats[2].details
    assert contradiction["winner"] == "parts_shortage"
    assert contradiction["decision"] == "accept_new"

    custom = result.beats[3].details
    assert custom["decision"] == "escalate"
    assert custom["human_choice"] == "wets"

    assert result.beats[4].details["diverged"]  # branch diverged from original
    assert result.scaling is not None
