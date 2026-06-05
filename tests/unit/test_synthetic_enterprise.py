"""Tests for the large synthetic enterprise dataset generator.

All deterministic (seeded) and network-free: assert the generators produce
coherent, scope-tagged data keyed to the calendar, at the expected scale, and
reproducibly.
"""

from demo.f1_race_weekend.synthesised.generate import (
    aero_configs,
    calendar_from_results,
    generate_enterprise,
    parts_consumption,
    parts_inventory,
)

# A small two-season calendar (modern, so it passes the enterprise start filter).
_CAL = [
    {"season": 2023, "round": 1, "circuit": "Bahrain", "date": "2023-03-05"},
    {"season": 2023, "round": 2, "circuit": "Jeddah", "date": "2023-03-19"},
    {"season": 2024, "round": 1, "circuit": "Bahrain", "date": "2024-03-02"},
    {"season": 2024, "round": 2, "circuit": "Jeddah", "date": "2024-03-09"},
]


def test_parts_inventory_has_critical_fw07_short():
    inv = {p["part_id"]: p for p in parts_inventory()}
    assert "FW-07" in inv
    assert inv["FW-07"]["stock"] == 2 and inv["FW-07"]["race_requirement"] == 4


def test_parts_consumption_keyed_to_calendar_and_scaled():
    rows = parts_consumption(_CAL, start_season=2010)
    # Only modern calendar rounds appear, each tagged for the parts scope.
    assert rows, "expected consumption rows"
    assert {r["season"] for r in rows} == {2023, 2024}
    assert all(r["topics"] == ["parts"] for r in rows)
    assert all(r["circuit"] in {"Bahrain", "Jeddah"} for r in rows)


def test_aero_configs_per_season_circuit_scoped():
    rows = aero_configs(_CAL, start_season=2010)
    # 2 seasons × 2 circuits = 4 configs.
    assert len(rows) == 4
    assert all(r["topics"] == ["aero"] for r in rows)
    assert all(1400 <= r["downforce_target_kg"] <= 1950 for r in rows)


def test_start_season_filters_out_old_seasons():
    cal = _CAL + [{"season": 1995, "round": 1, "circuit": "Interlagos", "date": "1995-03-26"}]
    rows = aero_configs(cal, start_season=2010)
    assert all(r["season"] >= 2010 for r in rows)


def test_generate_enterprise_is_deterministic_and_complete():
    a = generate_enterprise(_CAL, seed=7, start_season=2010)
    b = generate_enterprise(_CAL, seed=7, start_season=2010)
    assert a == b  # reproducible
    expected = {
        "parts_bom", "parts_inventory", "parts_consumption", "aero_configs",
        "car_setups", "supplier_contracts", "freight_logistics",
        "crew_clearances", "rd_experiments",
    }
    assert set(a) == expected
    assert len(a["parts_bom"]) > 100  # a real BOM, not a toy
    assert a["freight_logistics"][0]["topics"] == ["logistics", "calendar"]


def test_calendar_from_results_dedupes_by_season_round():
    results = [
        {"season": 2024, "round": 1, "circuit": "Bahrain", "date": "2024-03-02", "driver": "VER"},
        {"season": 2024, "round": 1, "circuit": "Bahrain", "date": "2024-03-02", "driver": "PER"},
        {"season": 2024, "round": 2, "circuit": "Jeddah", "date": "2024-03-09", "driver": "VER"},
    ]
    cal = calendar_from_results(results)
    assert len(cal) == 2  # two unique rounds despite 3 result rows
