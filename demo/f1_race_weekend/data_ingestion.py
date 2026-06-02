"""Demo data ingestion — real F1 sources + synthesised team systems → MongoDB.

Public sources (no auth, JSON over REST, fetched with httpx):
  - Jolpica (Ergast-compatible): race results, schedule, qualifying.
  - OpenF1: sessions + weather for the weekend.
Synthesised team systems (parts inventory, R&D, supplier contracts) come from
``demo.f1_race_weekend.synthesised``.

``build_dataset`` stays as the offline corpus (synthesised + a small results
fixture) so tests and the offline demo never hit the network. ``build_live_dataset``
fetches the real sources; ``ingest_to_mongo`` upserts whatever corpus it's given
into Atlas. Run it (in the dev container) with:

    docker compose run --rm app uv run python -m demo.f1_race_weekend.data_ingestion

Heavier sources defined in HANDOFF (FastF1 telemetry, the BigQuery public F1
dataset, Snowflake history) need extra deps/credentials and are wired separately.
"""

from __future__ import annotations

import os
from typing import Optional

import httpx

from demo.f1_race_weekend.synthesised.data import all_collections

JOLPICA_URL = os.environ.get("EZRA_JOLPICA_API_URL", "https://api.jolpi.ca/ergast/f1")
OPENF1_URL = os.environ.get("EZRA_OPENF1_API_URL", "https://api.openf1.org/v1")

# Small public-results fixture for the OFFLINE corpus (no network).
RACE_RESULTS_FIXTURE: list[dict] = [
    {"season": 2025, "round": 8, "circuit": "Monaco", "winner": "VER",
     "fastest_lap": "NOR", "topics": ["strategy"]},
    {"season": 2024, "round": 8, "circuit": "Monaco", "winner": "LEC",
     "fastest_lap": "HAM", "topics": ["strategy"]},
]


def build_dataset() -> dict[str, list[dict]]:
    """Offline demo corpus: synthesised team systems + a race-results fixture."""
    data = all_collections()
    data["race_results"] = list(RACE_RESULTS_FIXTURE)
    return data


# --------------------------------------------------------------------------- #
# Live source fetchers (Jolpica / OpenF1). Each takes an injected AsyncClient so
# tests drive them with httpx.MockTransport — no real network.
# --------------------------------------------------------------------------- #
async def _get_json(client: httpx.AsyncClient, url: str, params: Optional[dict] = None):
    resp = await client.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


async def fetch_jolpica_results(
    client: httpx.AsyncClient, *, season: int, circuit: str = "monaco"
) -> list[dict]:
    payload = await _get_json(client, f"{JOLPICA_URL}/{season}/circuits/{circuit}/results.json")
    races = payload.get("MRData", {}).get("RaceTable", {}).get("Races", [])
    if not races:
        return []
    race = races[0]
    out = []
    for r in race.get("Results", []):
        driver = r.get("Driver", {})
        out.append({
            "season": season,
            "round": race.get("round"),
            "circuit": race.get("Circuit", {}).get("circuitName"),
            "position": r.get("position"),
            "driver": driver.get("code") or driver.get("familyName"),
            "constructor": r.get("Constructor", {}).get("name"),
            "grid": r.get("grid"),
            "status": r.get("status"),
            "time": r.get("Time", {}).get("time"),
            "points": r.get("points"),
            "topics": ["strategy"],
        })
    return out


async def fetch_jolpica_schedule(client: httpx.AsyncClient, *, season: int) -> list[dict]:
    payload = await _get_json(client, f"{JOLPICA_URL}/{season}.json")
    races = payload.get("MRData", {}).get("RaceTable", {}).get("Races", [])
    return [{
        "season": season,
        "round": race.get("round"),
        "race_name": race.get("raceName"),
        "circuit": race.get("Circuit", {}).get("circuitName"),
        "date": race.get("date"),
        "topics": ["calendar"],
    } for race in races]


async def fetch_jolpica_qualifying(
    client: httpx.AsyncClient, *, season: int, circuit: str = "monaco"
) -> list[dict]:
    payload = await _get_json(client, f"{JOLPICA_URL}/{season}/circuits/{circuit}/qualifying.json")
    races = payload.get("MRData", {}).get("RaceTable", {}).get("Races", [])
    if not races:
        return []
    out = []
    for q in races[0].get("QualifyingResults", []):
        driver = q.get("Driver", {})
        out.append({
            "season": season,
            "circuit": races[0].get("Circuit", {}).get("circuitName"),
            "position": q.get("position"),
            "driver": driver.get("code") or driver.get("familyName"),
            "constructor": q.get("Constructor", {}).get("name"),
            "q1": q.get("Q1"), "q2": q.get("Q2"), "q3": q.get("Q3"),
            "topics": ["strategy", "tyres"],
        })
    return out


async def fetch_openf1_sessions(
    client: httpx.AsyncClient, *, year: int, country: str = "Monaco"
) -> list[dict]:
    rows = await _get_json(client, f"{OPENF1_URL}/sessions", {"country_name": country, "year": year})
    return [{
        "session_key": s.get("session_key"),
        "session_name": s.get("session_name"),
        "date_start": s.get("date_start"),
        "circuit_short_name": s.get("circuit_short_name"),
        "year": year,
        "topics": ["telemetry"],
    } for s in rows]


async def fetch_openf1_weather(
    client: httpx.AsyncClient, *, session_key: int, limit: int = 20
) -> list[dict]:
    rows = await _get_json(client, f"{OPENF1_URL}/weather", {"session_key": session_key})
    out = []
    for w in rows[:limit]:
        out.append({
            "session_key": session_key,
            "date": w.get("date"),
            "air_temperature": w.get("air_temperature"),
            "track_temperature": w.get("track_temperature"),
            "rainfall": w.get("rainfall"),
            "humidity": w.get("humidity"),
            "wind_speed": w.get("wind_speed"),
            "topics": ["weather"],
        })
    return out


# --------------------------------------------------------------------------- #
# Heavier sources — BigQuery public F1 dataset + FastF1 timing. Their SDKs are
# lazy/injected so the lean API image and the unit tests never need them; on GKE
# the ingest image carries them and BigQuery auths keyless via Workload Identity.
# --------------------------------------------------------------------------- #
_BQ_F1_QUERY = """
SELECT r.year, r.round, c.name AS circuit, d.code AS driver,
       res.positionOrder AS position, res.points
FROM `bigquery-public-data.formula_1.results` res
JOIN `bigquery-public-data.formula_1.races` r ON res.raceId = r.raceId
JOIN `bigquery-public-data.formula_1.circuits` c ON r.circuitId = c.circuitId
JOIN `bigquery-public-data.formula_1.drivers` d ON res.driverId = d.driverId
WHERE LOWER(c.name) LIKE @circuit
ORDER BY r.year DESC, res.positionOrder
LIMIT @row_limit
"""


def fetch_bigquery_f1(
    bq_client=None, *, project: str = "", circuit: str = "monaco", row_limit: int = 100
) -> list[dict]:
    """Query the public BigQuery F1 dataset for a circuit's historical results.

    Pass ``bq_client`` in tests; in the GKE job it's created from ADC (Workload
    Identity) with the billing project.
    """
    if bq_client is None:
        from google.cloud import bigquery  # lazy — only on the ingest image

        bq_client = bigquery.Client(project=project or None)

    # Parameterised when the SDK is present (GKE); tests inject a client and the
    # SDK is absent, so fall back to the bare query.
    try:
        from google.cloud import bigquery

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("circuit", "STRING", f"%{circuit.lower()}%"),
                bigquery.ScalarQueryParameter("row_limit", "INT64", row_limit),
            ]
        )
        rows = bq_client.query(_BQ_F1_QUERY, job_config=job_config).result()
    except ImportError:
        rows = bq_client.query(_BQ_F1_QUERY).result()
    return [{
        "year": row["year"], "round": row["round"], "circuit": row["circuit"],
        "driver": row["driver"], "position": row["position"], "points": row["points"],
        "topics": ["strategy"],
    } for row in rows]


def _default_fastf1_loader(year: int, event: str, session_type: str, cache_dir: str) -> list[dict]:
    import fastf1  # lazy — only on the ingest image

    os.makedirs(cache_dir, exist_ok=True)
    fastf1.Cache.enable_cache(cache_dir)
    session = fastf1.get_session(year, event, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    return session.results.to_dict("records")


def fetch_fastf1_session(
    loader=None, *, year: int = 2024, event: str = "Monaco",
    session_type: str = "R", cache_dir: Optional[str] = None,
) -> list[dict]:
    """Load a session's results via FastF1. ``loader`` is injected in tests."""
    cache_dir = cache_dir or os.environ.get("EZRA_FASTF1_CACHE_DIR", "/tmp/fastf1_cache")
    records = (loader or _default_fastf1_loader)(year, event, session_type, cache_dir)
    return [{
        "year": year, "event": event, "session": session_type,
        "driver": r.get("Abbreviation"), "team": r.get("TeamName"),
        "position": r.get("Position"), "points": r.get("Points"),
        "status": r.get("Status"), "topics": ["telemetry", "strategy"],
    } for r in records]


async def build_live_dataset(
    *,
    season: int = 2024,
    year: int = 2024,
    client: Optional[httpx.AsyncClient] = None,
    include_bigquery: bool = False,
    include_fastf1: bool = False,
    bq_client=None,
    bq_project: str = "",
    fastf1_loader=None,
) -> dict[str, list[dict]]:
    """Fetch the real public F1 data and merge it with the synthesised systems.

    Jolpica + OpenF1 (lightweight REST) always run. BigQuery and FastF1 are opt-in
    (they need the ingest deps + credentials) and run on the GKE ingest job.
    """
    own = client is None
    client = client or httpx.AsyncClient(timeout=30.0)
    try:
        data = all_collections()
        data["race_results"] = await fetch_jolpica_results(client, season=season)
        data["race_calendar"] = await fetch_jolpica_schedule(client, season=season)
        data["qualifying"] = await fetch_jolpica_qualifying(client, season=season)
        sessions = await fetch_openf1_sessions(client, year=year)
        data["sessions"] = sessions
        race = next((s for s in sessions if s.get("session_name") == "Race"), None)
        data["weather"] = (
            await fetch_openf1_weather(client, session_key=race["session_key"]) if race else []
        )
        if include_bigquery:
            data["historical_results"] = fetch_bigquery_f1(bq_client, project=bq_project)
        if include_fastf1:
            data["session_timing"] = fetch_fastf1_session(fastf1_loader, year=year)
        return data
    finally:
        if own:
            await client.aclose()


async def ingest_to_mongo(client, db_name: str, *, dataset: Optional[dict] = None) -> dict[str, int]:
    """Upsert a corpus into MongoDB. Returns per-collection row counts."""
    data = dataset if dataset is not None else build_dataset()
    counts: dict[str, int] = {}
    db = client[db_name]
    for name, rows in data.items():
        if rows:
            await db[name].delete_many({})
            await db[name].insert_many([dict(r) for r in rows])
        counts[name] = len(rows)
    return counts


async def _main() -> None:  # pragma: no cover - script entry point
    from pymongo import AsyncMongoClient

    from ezra_core.config import EzraSettings
    from ezra_core.secret_files import load_secret_files

    load_secret_files()  # GKE: pull Atlas URI from the Secret Manager CSI mount
    settings = EzraSettings()
    if not settings.mongodb_uri:
        raise SystemExit("EZRA_MONGODB_URI is not set — cannot ingest to Atlas.")

    # On GKE these are on by default; locally they need the `ingest` deps + auth,
    # so allow opting out via env.
    include_bigquery = os.environ.get("EZRA_INGEST_BIGQUERY", "true").lower() == "true"
    include_fastf1 = os.environ.get("EZRA_INGEST_FASTF1", "true").lower() == "true"
    project = os.environ.get("EZRA_GCP_PROJECT_ID", "")

    print(f"Fetching F1 data (Jolpica + OpenF1"
          f"{' + BigQuery' if include_bigquery else ''}"
          f"{' + FastF1' if include_fastf1 else ''})…")
    dataset = await build_live_dataset(
        include_bigquery=include_bigquery, include_fastf1=include_fastf1, bq_project=project
    )
    client = AsyncMongoClient(settings.mongodb_uri)
    counts = await ingest_to_mongo(client, settings.mongodb_db, dataset=dataset)
    for name, n in counts.items():
        print(f"  {name}: {n}")
    print("Done.")


if __name__ == "__main__":  # pragma: no cover
    import asyncio

    asyncio.run(_main())
