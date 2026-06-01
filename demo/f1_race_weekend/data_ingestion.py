"""Demo data ingestion.

Session-5 choice (user, 2026-06-01): synthesised data + static fixtures now so
the demo runs fully offline and tests stay network-free; live Jolpica / OpenF1 /
FastF1 ingestion is wired as a separate step once container egress is confirmed.

``build_dataset`` returns the full demo corpus (synthesised team systems + a
small fixture of public race results). ``ingest_to_mongo`` upserts it into Atlas
collections. The live fetchers are declared but deferred — they raise a clear
error rather than silently returning empty, so a caller can't mistake a stub for
real data.
"""

from __future__ import annotations

from typing import Optional

from demo.f1_race_weekend.synthesised.data import all_collections

# Small public-results fixture (stands in for Jolpica/Ergast until live wiring).
RACE_RESULTS_FIXTURE: list[dict] = [
    {"season": 2025, "round": 8, "circuit": "Monaco", "winner": "VER",
     "fastest_lap": "NOR", "topics": ["strategy"]},
    {"season": 2024, "round": 8, "circuit": "Monaco", "winner": "LEC",
     "fastest_lap": "HAM", "topics": ["strategy"]},
]


def build_dataset() -> dict[str, list[dict]]:
    """The full offline demo corpus: synthesised team systems + race results."""
    data = all_collections()
    data["race_results"] = list(RACE_RESULTS_FIXTURE)
    return data


async def ingest_to_mongo(client, db_name: str, *, dataset: Optional[dict] = None) -> dict[str, int]:
    """Upsert the demo corpus into MongoDB. Returns per-collection counts."""
    data = dataset if dataset is not None else build_dataset()
    counts: dict[str, int] = {}
    db = client[db_name]
    for name, rows in data.items():
        if rows:
            await db[name].delete_many({})
            await db[name].insert_many([dict(r) for r in rows])
        counts[name] = len(rows)
    return counts


# --------------------------------------------------------------------------- #
# Live sources — deferred (HANDOFF Session 5). Kept explicit so they are not
# mistaken for working ingestion.
# --------------------------------------------------------------------------- #
def fetch_jolpica_results(*args, **kwargs):  # pragma: no cover - deferred
    raise NotImplementedError(
        "Live Jolpica ingestion is deferred; demo uses RACE_RESULTS_FIXTURE."
    )


def fetch_openf1_live(*args, **kwargs):  # pragma: no cover - deferred
    raise NotImplementedError(
        "Live OpenF1 ingestion is deferred; demo uses synthesised telemetry."
    )
