"""Large synthetic enterprise dataset — the private team systems Ezra federates
over that have NO public source (aero R&D, parts inventory + consumption, supplier
contracts, freight logistics, crew clearances, car setups).

Everything is generated deterministically from a seed and keyed to the real race
calendar (passed in from the fetched results), so the synthetic data is coherent
with the public race data: parts get consumed at real rounds, aero configs exist
per real circuit/season, freight ships to the real calendar. Volume scales with
the season range — multi-season parts consumption alone is tens of thousands of
rows — to back the "large distributed dataset" story.

The small fixtures in ``data.py`` stay as the offline-demo corpus; this module is
for the wide ingest. Every row carries ``topics`` for permission-scope filtering.
"""

from __future__ import annotations

import random

# Default: enterprise systems only make sense for the modern (fictional Team Ezra)
# era — generating fake aero/freight for 1950 would be incoherent.
ENTERPRISE_START_SEASON = 2010

# --------------------------------------------------------------------------- #
# Reference vocabularies
# --------------------------------------------------------------------------- #
_SUBSYSTEMS = {
    "FW": ("Front wing", "aero", True),
    "RW": ("Rear wing", "aero", True),
    "FL": ("Floor", "aero", True),
    "DIF": ("Diffuser", "aero", True),
    "SP": ("Sidepod", "aero", False),
    "BRK": ("Brake duct", "brakes", True),
    "SUS": ("Suspension arm", "suspension", True),
    "GBX": ("Gearbox", "power_unit", False),
    "PU": ("Power unit element", "power_unit", False),
    "ERS": ("ERS module", "power_unit", False),
    "HALO": ("Halo", "chassis", False),
    "NOSE": ("Nose cone", "chassis", True),
    "STW": ("Steering wheel", "electronics", False),
    "MGU": ("MGU-K", "power_unit", False),
}

_SUPPLIERS = [
    ("Brembo", "brakes"), ("Pirelli", "tyres"), ("Carbon Dynamics", "front wing"),
    ("Mahle", "pistons"), ("BorgWarner", "turbo"), ("Sabelt", "seatbelts"),
    ("OZ Racing", "wheels"), ("AP Racing", "clutch"), ("Magneti Marelli", "electronics"),
    ("PWR", "radiators"), ("Akebono", "brake pads"), ("Garrett", "turbocharger"),
    ("Bosch", "sensors"), ("Shell", "fuel"), ("Petronas", "lubricants"),
    ("Zeiss", "metrology"), ("Siemens", "PLM software"), ("Dassault", "CFD licenses"),
    ("3M", "adhesives"), ("Henkel", "composites"),
]

_CREW_ROLES = [
    "Race Engineer", "Performance Engineer", "Mechanic", "Tyre Technician",
    "Aerodynamicist", "Strategist", "Data Analyst", "Garage Technician",
    "Hospitality", "Logistics Coordinator", "Security Officer", "Media Officer",
]
_CLEARANCE_LEVELS = ["paddock", "garage", "pit_wall", "restricted_tech", "full"]

_FREIGHT_ORIGINS = ["Brackley UK", "Maranello IT", "Milton Keynes UK", "Hinwil CH"]
_FREIGHT_MODES = ["air", "sea", "road"]

_AERO_LEVELS = ["low_downforce", "medium", "high_downforce", "max_downforce"]


def _rng(seed: int, *salt) -> random.Random:
    return random.Random((seed, *salt).__hash__())


def _calendar_seasons(calendar: list[dict], start_season: int) -> list[int]:
    seasons = sorted({int(r["season"]) for r in calendar if int(r.get("season", 0)) >= start_season})
    return seasons


def _circuits_in(calendar: list[dict], start_season: int) -> list[str]:
    return sorted({
        r.get("circuit") for r in calendar
        if r.get("circuit") and int(r.get("season", 0)) >= start_season
    })


# --------------------------------------------------------------------------- #
# Generators
# --------------------------------------------------------------------------- #
def parts_bom(seed: int = 7) -> list[dict]:
    """The full bill of materials — ~250 parts across subsystems/variants."""
    rng = _rng(seed, "bom")
    out: list[dict] = []
    for code, (name, area, consumable) in _SUBSYSTEMS.items():
        for variant in range(1, 21):  # 14 subsystems × 20 variants ≈ 280 parts
            pid = f"{code}-{variant:02d}"
            out.append({
                "part_id": pid,
                "name": f"{name} spec {variant}",
                "subsystem": code,
                "area": area,
                "consumable": consumable,
                "unit_cost_gbp": rng.choice([1500, 3000, 8000, 15000, 40000, 120000]),
                "supplier": rng.choice([s[0] for s in _SUPPLIERS]),
                "topics": ["parts", area] if area == "aero" else ["parts"],
            })
    return out


def parts_inventory(seed: int = 7) -> list[dict]:
    """Current stock snapshot per part. FW-07 is intentionally short (demo beat)."""
    rng = _rng(seed, "inv")
    out = []
    for part in parts_bom(seed):
        req = rng.randint(2, 6)
        stock = rng.randint(0, 12)
        out.append({
            "part_id": part["part_id"],
            "name": part["name"],
            "stock": stock,
            "race_requirement": req,
            "reorder_threshold": max(2, req - 1),
            "topics": ["parts"],
        })
    # Force the demo's critical short: FW-07 → 2 in stock vs 4 needed.
    for row in out:
        if row["part_id"] == "FW-07":
            row.update(stock=2, race_requirement=4, reorder_threshold=3)
    return out


def parts_consumption(calendar: list[dict], *, seed: int = 7,
                      start_season: int = ENTERPRISE_START_SEASON) -> list[dict]:
    """Per-round consumption for consumable parts — the high-volume collection."""
    bom = [p for p in parts_bom(seed) if p["consumable"]]
    out: list[dict] = []
    for race in calendar:
        season = int(race.get("season", 0))
        if season < start_season:
            continue
        rng = _rng(seed, "cons", season, race.get("round"))
        for part in bom:
            qty = rng.randint(0, 4)
            if qty == 0:
                continue
            out.append({
                "season": season,
                "round": int(race.get("round", 0)),
                "circuit": race.get("circuit"),
                "date": race.get("date"),
                "part_id": part["part_id"],
                "qty_used": qty,
                "failures": rng.choice([0, 0, 0, 1]),
                "topics": ["parts"],
            })
    return out


def aero_configs(calendar: list[dict], *, seed: int = 7,
                 start_season: int = ENTERPRISE_START_SEASON) -> list[dict]:
    """Per season/circuit aerodynamic configuration + CFD/wind-tunnel effort."""
    out: list[dict] = []
    for season in _calendar_seasons(calendar, start_season):
        for circuit in _circuits_in([r for r in calendar if int(r.get("season", 0)) == season], start_season):
            rng = _rng(seed, "aero", season, circuit)
            level = rng.choice(_AERO_LEVELS)
            out.append({
                "season": season,
                "circuit": circuit,
                "downforce_level": level,
                "downforce_target_kg": rng.randint(1400, 1950),
                "drag_count": rng.randint(60, 130),
                "wing_spec": f"W{season % 100}-{rng.randint(1, 6)}",
                "cfd_runs": rng.randint(40, 400),
                "wind_tunnel_hours": rng.randint(10, 80),
                "topics": ["aero"],
            })
    return out


def car_setups(calendar: list[dict], *, seed: int = 7,
               start_season: int = ENTERPRISE_START_SEASON) -> list[dict]:
    out: list[dict] = []
    for season in _calendar_seasons(calendar, start_season):
        for circuit in _circuits_in([r for r in calendar if int(r.get("season", 0)) == season], start_season):
            rng = _rng(seed, "setup", season, circuit)
            out.append({
                "season": season,
                "circuit": circuit,
                "ride_height_mm": rng.randint(20, 45),
                "front_camber": round(rng.uniform(-3.5, -2.0), 2),
                "rear_camber": round(rng.uniform(-2.5, -1.0), 2),
                "suspension_stiffness": rng.choice(["soft", "medium", "stiff"]),
                "brake_bias_pct": round(rng.uniform(52.0, 58.0), 1),
                "topics": ["setup", "strategy"],
            })
    return out


def supplier_contracts(seed: int = 7) -> list[dict]:
    rng = _rng(seed, "supp")
    out = []
    for name, component in _SUPPLIERS:
        out.append({
            "supplier": name,
            "component": component,
            "lead_time_days": rng.randint(1, 14),
            "penalty_clause": rng.choice([True, False]),
            "sla_pct": rng.choice([95.0, 97.5, 99.0, 99.9]),
            "annual_value_gbp": rng.choice([250_000, 500_000, 1_200_000, 3_000_000]),
            "topics": ["supplier", "parts"],
        })
    return out


def freight_logistics(calendar: list[dict], *, seed: int = 7,
                      start_season: int = ENTERPRISE_START_SEASON) -> list[dict]:
    out: list[dict] = []
    for race in calendar:
        season = int(race.get("season", 0))
        if season < start_season:
            continue
        rng = _rng(seed, "freight", season, race.get("round"))
        out.append({
            "season": season,
            "round": int(race.get("round", 0)),
            "circuit": race.get("circuit"),
            "date": race.get("date"),
            "origin": rng.choice(_FREIGHT_ORIGINS),
            "mode": rng.choice(_FREIGHT_MODES),
            "weight_kg": rng.randint(28_000, 52_000),
            "cost_gbp": rng.randint(120_000, 480_000),
            "customs_status": rng.choice(["cleared", "cleared", "pending", "inspection"]),
            "topics": ["logistics", "calendar"],
        })
    return out


def crew_clearances(seed: int = 7, *, headcount: int = 140) -> list[dict]:
    rng = _rng(seed, "crew")
    out = []
    for i in range(1, headcount + 1):
        role = rng.choice(_CREW_ROLES)
        out.append({
            "crew_id": f"EZ-{i:03d}",
            "role": role,
            "clearance_level": rng.choice(_CLEARANCE_LEVELS),
            "media_trained": rng.choice([True, False]),
            "topics": ["security", "crew"],
        })
    return out


def rd_experiments(calendar: list[dict], *, seed: int = 7,
                   start_season: int = ENTERPRISE_START_SEASON) -> list[dict]:
    out: list[dict] = []
    areas = ["aero", "power_unit", "suspension", "brakes", "tyres"]
    for season in _calendar_seasons(calendar, start_season):
        rng = _rng(seed, "rnd", season)
        for n in range(1, 13):
            area = rng.choice(areas)
            out.append({
                "experiment_id": f"RND-{season}-{n:02d}",
                "season": season,
                "title": f"{area} development {n}",
                "area": area,
                "status": rng.choice(["validated", "in_test", "shelved", "in_test"]),
                "target_gain_s": round(rng.uniform(0.02, 0.35), 3),
                "topics": ["aero"] if area == "aero" else ["strategy"],
            })
    return out


def generate_enterprise(calendar: list[dict], *, seed: int = 7,
                        start_season: int = ENTERPRISE_START_SEASON) -> dict[str, list[dict]]:
    """All synthetic enterprise collections, keyed to ``calendar``.

    ``calendar`` is a list of race dicts with season/round/circuit/date (derive it
    from the fetched race results). Returns a dict of collection name -> rows.
    """
    return {
        "parts_bom": parts_bom(seed),
        "parts_inventory": parts_inventory(seed),
        "parts_consumption": parts_consumption(calendar, seed=seed, start_season=start_season),
        "aero_configs": aero_configs(calendar, seed=seed, start_season=start_season),
        "car_setups": car_setups(calendar, seed=seed, start_season=start_season),
        "supplier_contracts": supplier_contracts(seed),
        "freight_logistics": freight_logistics(calendar, seed=seed, start_season=start_season),
        "crew_clearances": crew_clearances(seed),
        "rd_experiments": rd_experiments(calendar, seed=seed, start_season=start_season),
    }


def calendar_from_results(results: list[dict]) -> list[dict]:
    """Derive a unique (season, round, circuit, date) calendar from race results."""
    seen: dict[tuple, dict] = {}
    for r in results:
        key = (r.get("season"), r.get("round"))
        if key not in seen and r.get("round") is not None:
            seen[key] = {
                "season": r.get("season"),
                "round": r.get("round"),
                "circuit": r.get("circuit"),
                "date": r.get("date"),
            }
    return list(seen.values())
