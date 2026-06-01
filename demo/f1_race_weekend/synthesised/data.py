"""Synthesised enterprise datasets for the F1 demo (realistic numbers).

These stand in for the private team systems Ezra federates over (parts inventory,
R&D experiments, supplier contracts) alongside the public race data. The front
wing FW-07 is intentionally short — 2 in stock against a race need of 4 — which
drives the conditional ``parts_shortage`` spawn and the highest-trust
contradiction beat.
"""

from __future__ import annotations


def parts_inventory() -> list[dict]:
    return [
        {"part_id": "FW-07", "name": "Front wing assembly", "stock": 2,
         "race_requirement": 4, "reorder_threshold": 3, "topics": ["parts"]},
        {"part_id": "RW-03", "name": "Rear wing assembly", "stock": 5,
         "race_requirement": 3, "reorder_threshold": 2, "topics": ["parts"]},
        {"part_id": "FL-12", "name": "Floor edge wing", "stock": 6,
         "race_requirement": 2, "reorder_threshold": 2, "topics": ["parts"]},
        {"part_id": "BRK-09", "name": "Brake duct set", "stock": 8,
         "race_requirement": 4, "reorder_threshold": 3, "topics": ["parts"]},
    ]


def rd_experiments() -> list[dict]:
    return [
        {"experiment_id": "AERO-MON-01", "title": "High-downforce Monaco wing",
         "downforce_target_kg": 1850, "status": "validated", "topics": ["aero"]},
        {"experiment_id": "AERO-MON-02", "title": "Low-drag alternative",
         "downforce_target_kg": 1720, "status": "in_test", "topics": ["aero"]},
    ]


def supplier_contracts() -> list[dict]:
    return [
        {"supplier": "Brembo", "component": "brakes", "lead_time_days": 5,
         "penalty_clause": True, "topics": ["supplier", "parts"]},
        {"supplier": "Pirelli", "component": "tyres", "lead_time_days": 1,
         "penalty_clause": False, "topics": ["supplier", "tyres"]},
        {"supplier": "Carbon Dynamics", "component": "front wing", "lead_time_days": 9,
         "penalty_clause": True, "topics": ["supplier", "parts"]},
    ]


def all_collections() -> dict[str, list[dict]]:
    return {
        "parts_inventory": parts_inventory(),
        "rd_experiments": rd_experiments(),
        "supplier_contracts": supplier_contracts(),
    }
