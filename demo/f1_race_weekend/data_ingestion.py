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

import asyncio
import os
from typing import AsyncIterator, Optional

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


async def fetch_openf1_stints(client: httpx.AsyncClient, *, session_key: int) -> list[dict]:
    """Real tyre stints (compound + age) — core data for the tyre engineer."""
    rows = await _get_json(client, f"{OPENF1_URL}/stints", {"session_key": session_key})
    return [{
        "session_key": session_key,
        "driver_number": s.get("driver_number"),
        "stint_number": s.get("stint_number"),
        "compound": s.get("compound"),
        "lap_start": s.get("lap_start"),
        "lap_end": s.get("lap_end"),
        "tyre_age_at_start": s.get("tyre_age_at_start"),
        "topics": ["tyres", "telemetry"],
    } for s in rows]


async def fetch_openf1_pit(client: httpx.AsyncClient, *, session_key: int) -> list[dict]:
    """Real pit stops — pit lane duration per stop (race strategy)."""
    rows = await _get_json(client, f"{OPENF1_URL}/pit", {"session_key": session_key})
    return [{
        "session_key": session_key,
        "driver_number": p.get("driver_number"),
        "lap_number": p.get("lap_number"),
        "pit_duration": p.get("pit_duration"),
        "date": p.get("date"),
        "topics": ["strategy", "telemetry"],
    } for p in rows]


async def fetch_openf1_race_control(
    client: httpx.AsyncClient, *, session_key: int
) -> list[dict]:
    """Real FIA race-control messages (flags, safety cars, penalties) — press/strategy."""
    rows = await _get_json(client, f"{OPENF1_URL}/race_control", {"session_key": session_key})
    return [{
        "session_key": session_key,
        "date": rc.get("date"),
        "category": rc.get("category"),
        "flag": rc.get("flag"),
        "message": rc.get("message"),
        "scope": rc.get("scope"),
        "topics": ["press", "strategy"],
    } for rc in rows]


# --------------------------------------------------------------------------- #
# Heavier sources — BigQuery public F1 dataset + FastF1 timing. Their SDKs are
# lazy/injected so the lean API image and the unit tests never need them; on GKE
# the ingest image carries them and BigQuery auths keyless via Workload Identity.
# --------------------------------------------------------------------------- #
# There is no `bigquery-public-data.formula_1` dataset (verified) — we load
# historical Monaco results from Ergast into our own table and query that, which
# also makes the BigQuery mesh connector (time-travel) demoable on data we own.
_BQ_F1_TABLE = os.environ.get("EZRA_BQ_F1_TABLE", "ezra-498021.formula_1.monaco_results")


def fetch_bigquery_f1(
    bq_client=None, *, project: str = "", table: Optional[str] = None, row_limit: int = 100
) -> list[dict]:
    """Query our BigQuery F1 results table for historical (multi-season) results.

    Pass ``bq_client`` in tests; in the GKE job it's created from ADC (Workload
    Identity). The table name is a trusted env/config value (not user input), so
    it's inlined — BigQuery can't bind a table name as a query parameter.
    """
    table = table or _BQ_F1_TABLE
    query = (
        f"SELECT season, round, circuit, driver, constructor, position, points "
        f"FROM `{table}` ORDER BY season DESC LIMIT {int(row_limit)}"
    )
    if bq_client is None:
        from google.cloud import bigquery  # lazy — only on the ingest image

        bq_client = bigquery.Client(project=project or None)

    rows = bq_client.query(query).result()
    return [{
        "season": row["season"], "round": row["round"], "circuit": row["circuit"],
        "driver": row["driver"], "constructor": row["constructor"],
        "position": row["position"], "points": row["points"],
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


# --------------------------------------------------------------------------- #
# Wide historical spine — the full Ergast/Jolpica back-catalogue, paginated.
# Jolpica is a free community API with rate limits, so every page is polite
# (small delay) and retries on 429. ``build_wide_dataset`` loops seasons to build
# a genuinely large, multi-collection federated corpus (results + standings +
# reference circuits) on top of the synthesised team systems.
# --------------------------------------------------------------------------- #
async def _get_json_retrying(
    client: httpx.AsyncClient, url: str, params: dict, *, max_retries: int = 4
):
    """GET JSON, backing off on 429/5xx (Jolpica rate-limits unauthenticated)."""
    delay = 1.0
    for attempt in range(max_retries + 1):
        resp = await client.get(url, params=params)
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= 2
                continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()
    return resp.json()


async def _ergast_pages(
    client: httpx.AsyncClient,
    path: str,
    *,
    limit: int = 100,
    polite_delay: float = 0.3,
    max_rows: Optional[int] = None,
) -> AsyncIterator[dict]:
    """Yield each page's ``MRData`` for an Ergast path, following limit/offset."""
    offset = 0
    while True:
        payload = await _get_json_retrying(
            client, f"{JOLPICA_URL}/{path}", {"limit": limit, "offset": offset}
        )
        mrdata = payload.get("MRData", {})
        yield mrdata
        total = int(mrdata.get("total", 0))
        offset += limit
        if offset >= total or (max_rows is not None and offset >= max_rows):
            break
        if polite_delay:
            await asyncio.sleep(polite_delay)


async def fetch_season_results(
    client: httpx.AsyncClient, *, season: int, polite_delay: float = 0.3
) -> list[dict]:
    """All race results for one season (every round), flattened to one row/result.

    Pagination may split a race across pages; flattening per result row makes that
    transparent — each result appears exactly once.
    """
    out: list[dict] = []
    async for mrdata in _ergast_pages(
        client, f"{season}/results.json", polite_delay=polite_delay
    ):
        for race in mrdata.get("RaceTable", {}).get("Races", []):
            for r in race.get("Results", []):
                driver = r.get("Driver", {})
                out.append({
                    "season": int(season),
                    "round": int(race.get("round", 0)),
                    "race_name": race.get("raceName"),
                    "circuit": race.get("Circuit", {}).get("circuitName"),
                    "date": race.get("date"),
                    "position": r.get("position"),
                    "driver": driver.get("code") or driver.get("familyName"),
                    "constructor": r.get("Constructor", {}).get("name"),
                    "grid": r.get("grid"),
                    "status": r.get("status"),
                    "points": r.get("points"),
                    "topics": ["strategy"],
                })
    return out


async def fetch_driver_standings(client: httpx.AsyncClient, *, season: int) -> list[dict]:
    payload = await _get_json_retrying(
        client, f"{JOLPICA_URL}/{season}/driverStandings.json", {}
    )
    lists = payload.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])
    if not lists:
        return []
    out = []
    for s in lists[0].get("DriverStandings", []):
        driver = s.get("Driver", {})
        cons = s.get("Constructors", [{}])
        out.append({
            "season": int(season),
            "position": s.get("position"),
            "points": s.get("points"),
            "wins": s.get("wins"),
            "driver": driver.get("code") or driver.get("familyName"),
            "constructor": cons[0].get("name") if cons else None,
            "topics": ["strategy"],
        })
    return out


async def fetch_constructor_standings(
    client: httpx.AsyncClient, *, season: int
) -> list[dict]:
    payload = await _get_json_retrying(
        client, f"{JOLPICA_URL}/{season}/constructorStandings.json", {}
    )
    lists = payload.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])
    if not lists:
        return []
    return [{
        "season": int(season),
        "position": s.get("position"),
        "points": s.get("points"),
        "wins": s.get("wins"),
        "constructor": s.get("Constructor", {}).get("name"),
        "topics": ["strategy"],
    } for s in lists[0].get("ConstructorStandings", [])]


async def fetch_circuits(
    client: httpx.AsyncClient, *, polite_delay: float = 0.3
) -> list[dict]:
    """All circuits Ergast knows about (reference data, paginated)."""
    out: list[dict] = []
    async for mrdata in _ergast_pages(client, "circuits.json", polite_delay=polite_delay):
        for c in mrdata.get("CircuitTable", {}).get("Circuits", []):
            loc = c.get("Location", {})
            out.append({
                "circuit_id": c.get("circuitId"),
                "circuit": c.get("circuitName"),
                "locality": loc.get("locality"),
                "country": loc.get("country"),
                "lat": loc.get("lat"),
                "long": loc.get("long"),
                "topics": ["calendar"],
            })
    return out


async def build_wide_dataset(
    *,
    seasons: range,
    client: Optional[httpx.AsyncClient] = None,
    polite_delay: float = 0.3,
    include_bigquery: bool = False,
    include_fastf1: bool = False,
    include_openf1: bool = True,
    include_enterprise: bool = True,
    openf1_seasons: Optional[range] = None,
    enterprise_start_season: int = 2010,
    bq_client=None,
    bq_project: str = "",
    fastf1_loader=None,
    fastf1_year: int = 2024,
) -> dict[str, list[dict]]:
    """Build the full historical corpus across ``seasons`` + the team systems.

    Loops every season for results + both standings, adds the all-time circuit
    reference, real OpenF1 telemetry (stints/pit/laps/race-control) for recent
    seasons, and a large synthetic enterprise dataset (aero / parts / supplier /
    freight / crew) keyed to the real calendar. Heavy sources (BigQuery, FastF1)
    are opt-in. One flaky source must not abort the whole grind.
    """
    own = client is None
    client = client or httpx.AsyncClient(timeout=60.0)

    async def _try(label, coro):
        try:
            return await coro
        except Exception as exc:
            print(f"WARN {label} failed: {exc}")
            return []

    try:
        data = all_collections()
        results: list[dict] = []
        d_standings: list[dict] = []
        c_standings: list[dict] = []
        for season in seasons:
            results += await _try(
                f"results.{season}",
                fetch_season_results(client, season=season, polite_delay=polite_delay),
            )
            d_standings += await _try(
                f"driverStandings.{season}", fetch_driver_standings(client, season=season)
            )
            c_standings += await _try(
                f"constructorStandings.{season}",
                fetch_constructor_standings(client, season=season),
            )
        data["race_results"] = results
        data["driver_standings"] = d_standings
        data["constructor_standings"] = c_standings
        data["circuits"] = await _try("circuits", fetch_circuits(client, polite_delay=polite_delay))

        # Real OpenF1 telemetry (2023+): stints, pit, laps, FIA race-control events.
        if include_openf1:
            of1_seasons = openf1_seasons or range(2023, (seasons.stop))
            data.update(await _try_openf1(client, of1_seasons, polite_delay))

        # Large synthetic enterprise dataset, keyed to the real calendar.
        if include_enterprise:
            from demo.f1_race_weekend.synthesised.generate import (
                calendar_from_results,
                generate_enterprise,
            )

            calendar = calendar_from_results(results)
            data.update(
                generate_enterprise(calendar, start_season=enterprise_start_season)
            )

        if include_bigquery:
            try:
                data["historical_results"] = fetch_bigquery_f1(bq_client, project=bq_project)
            except Exception as exc:
                print(f"WARN bigquery failed: {exc}")
        if include_fastf1:
            try:
                data["session_timing"] = fetch_fastf1_session(fastf1_loader, year=fastf1_year)
            except Exception as exc:
                print(f"WARN fastf1 failed: {exc}")
        return data
    finally:
        if own:
            await client.aclose()


async def _try_openf1(client, seasons: range, polite_delay: float) -> dict[str, list[dict]]:
    """Best-effort OpenF1 telemetry across ``seasons`` (real car/session data)."""
    out: dict[str, list[dict]] = {"stints": [], "pit_stops": [], "laps_summary": [],
                                  "race_control": [], "weather": []}
    for year in seasons:
        try:
            sessions = await fetch_openf1_sessions(client, year=year)
        except Exception as exc:
            print(f"WARN openf1.sessions.{year} failed: {exc}")
            continue
        races = [s for s in sessions if s.get("session_name") == "Race"]
        for s in races:
            key = s.get("session_key")
            if not key:
                continue
            for label, coro in (
                ("stints", fetch_openf1_stints(client, session_key=key)),
                ("pit_stops", fetch_openf1_pit(client, session_key=key)),
                ("race_control", fetch_openf1_race_control(client, session_key=key)),
                ("weather", fetch_openf1_weather(client, session_key=key)),
            ):
                try:
                    out[label] += await coro
                except Exception as exc:
                    print(f"WARN openf1.{label}.{key} failed: {exc}")
            if polite_delay:
                await asyncio.sleep(polite_delay)
    return out


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

    async def _try_async(label, coro):
        try:
            return await coro
        except Exception as exc:  # one flaky source must not abort the whole ingest
            print(f"WARN {label} failed: {exc}")
            return []

    def _try_sync(label, fn):
        try:
            return fn()
        except Exception as exc:
            print(f"WARN {label} failed: {exc}")
            return []

    try:
        data = all_collections()
        data["race_results"] = await _try_async("jolpica.results", fetch_jolpica_results(client, season=season))
        data["race_calendar"] = await _try_async("jolpica.schedule", fetch_jolpica_schedule(client, season=season))
        data["qualifying"] = await _try_async("jolpica.qualifying", fetch_jolpica_qualifying(client, season=season))
        sessions = await _try_async("openf1.sessions", fetch_openf1_sessions(client, year=year))
        data["sessions"] = sessions
        race = next((s for s in sessions if s.get("session_name") == "Race"), None)
        data["weather"] = (
            await _try_async("openf1.weather", fetch_openf1_weather(client, session_key=race["session_key"]))
            if race else []
        )
        if include_bigquery:
            data["historical_results"] = _try_sync(
                "bigquery", lambda: fetch_bigquery_f1(bq_client, project=bq_project)
            )
        if include_fastf1:
            data["session_timing"] = _try_sync(
                "fastf1", lambda: fetch_fastf1_session(fastf1_loader, year=year)
            )
        return data
    finally:
        if own:
            await client.aclose()


async def ingest_to_mongo(
    client, db_name: str, *, dataset: Optional[dict] = None, batch_size: int = 1000
) -> dict[str, int]:
    """Replace each collection with the corpus. Returns per-collection row counts.

    Inserts are chunked (``batch_size``) so the wide historical corpus — tens of
    thousands of result rows — doesn't exceed MongoDB's bulk-write limits.
    """
    data = dataset if dataset is not None else build_dataset()
    counts: dict[str, int] = {}
    db = client[db_name]
    for name, rows in data.items():
        if rows:
            await db[name].delete_many({})
            for start in range(0, len(rows), batch_size):
                chunk = [dict(r) for r in rows[start : start + batch_size]]
                await db[name].insert_many(chunk)
        counts[name] = len(rows)
    return counts


# --------------------------------------------------------------------------- #
# Snowflake load — historical race results into the warehouse the Snowflake mesh
# connector queries (the demo's "Snowflake: historical race results" source, with
# native AT(TIMESTAMP=>) time-travel). Lazy SDK import; runs only where wanted.
# --------------------------------------------------------------------------- #
_SF_RESULT_COLS = [
    ("SEASON", "INTEGER"), ("ROUND", "INTEGER"), ("RACE_NAME", "STRING"),
    ("CIRCUIT", "STRING"), ("RACE_DATE", "STRING"), ("POSITION", "STRING"),
    ("DRIVER", "STRING"), ("CONSTRUCTOR", "STRING"), ("GRID", "STRING"),
    ("STATUS", "STRING"), ("POINTS", "STRING"),
]


def load_results_to_snowflake(settings, rows: list[dict], *, batch_size: int = 5000) -> int:
    """Create EZRA.<schema>.RACE_RESULTS and load ``rows`` into it. Returns the
    row count. Synchronous (snowflake-connector is sync); call via asyncio.to_thread
    if needed. Idempotent: CREATE OR REPLACE drops and rebuilds the table."""
    import snowflake.connector

    db = settings.snowflake_database or "EZRA"
    schema = settings.snowflake_schema or "PUBLIC"
    conn = snowflake.connector.connect(
        account=settings.snowflake_account,
        user=settings.snowflake_user,
        password=settings.snowflake_password,
        role=settings.snowflake_role or None,
        warehouse=settings.snowflake_warehouse or None,
    )
    try:
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {db}")
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {db}.{schema}")
        cols_ddl = ", ".join(f"{name} {typ}" for name, typ in _SF_RESULT_COLS)
        cur.execute(f"CREATE OR REPLACE TABLE {db}.{schema}.RACE_RESULTS ({cols_ddl})")
        names = [c[0] for c in _SF_RESULT_COLS]
        placeholders = ", ".join(["%s"] * len(names))
        insert = f"INSERT INTO {db}.{schema}.RACE_RESULTS ({', '.join(names)}) VALUES ({placeholders})"
        keys = ["season", "round", "race_name", "circuit", "date", "position",
                "driver", "constructor", "grid", "status", "points"]
        params = [tuple(r.get(k) for k in keys) for r in rows]
        for start in range(0, len(params), batch_size):
            cur.executemany(insert, params[start : start + batch_size])
        conn.commit()
        return len(params)
    finally:
        conn.close()


def load_table_to_snowflake(settings, table: str, rows: list[dict], *, conn=None) -> int:
    """Generic Snowflake loader: CREATE OR REPLACE ``EZRA.<schema>.<table>`` with
    STRING columns derived from the row keys (``topics`` dropped), then load. Used
    for the warehouse's non-results tables (e.g. standings)."""
    import snowflake.connector

    db = settings.snowflake_database or "EZRA"
    schema = settings.snowflake_schema or "PUBLIC"
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k != "topics" and k not in cols:
                cols.append(k)
    own = conn is None
    conn = conn or snowflake.connector.connect(
        account=settings.snowflake_account, user=settings.snowflake_user,
        password=settings.snowflake_password, role=settings.snowflake_role or None,
        warehouse=settings.snowflake_warehouse or None,
    )
    try:
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {db}")
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {db}.{schema}")
        full = f"{db}.{schema}.{table.upper()}"
        coldefs = ", ".join(f'"{c.upper()}" STRING' for c in cols)
        cur.execute(f"CREATE OR REPLACE TABLE {full} ({coldefs})")
        names = ", ".join(f'"{c.upper()}"' for c in cols)
        placeholders = ", ".join(["%s"] * len(cols))
        insert = f"INSERT INTO {full} ({names}) VALUES ({placeholders})"
        params = [
            tuple(None if r.get(c) is None else str(r.get(c)) for c in cols) for r in rows
        ]
        for start in range(0, len(params), 5000):
            cur.executemany(insert, params[start : start + 5000])
        conn.commit()
        return len(params)
    finally:
        if own:
            conn.close()


def load_table_to_bigquery(settings, table: str, rows: list[dict], *, client=None) -> int:
    """Generic BigQuery loader: WRITE_TRUNCATE ``rows`` into ``table`` with schema
    autodetect (``topics`` dropped). Used for the engineering/aero analytics tables."""
    from google.cloud import bigquery

    project = table.split(".")[0]
    dataset_id = ".".join(table.split(".")[:2])
    if client is None:
        client = bigquery.Client(project=project)
    client.create_dataset(bigquery.Dataset(dataset_id), exists_ok=True)
    payload = [{k: v for k, v in r.items() if k != "topics"} for r in rows]
    job_config = bigquery.LoadJobConfig(autodetect=True, write_disposition="WRITE_TRUNCATE")
    client.load_table_from_json(payload, table, job_config=job_config).result()
    return len(payload)


def load_results_to_bigquery(
    settings, rows: list[dict], *, table: Optional[str] = None, client=None
) -> int:
    """Load ``rows`` into a BigQuery table (keyless via ADC / Workload Identity).

    Creates the dataset + table if needed and replaces its contents. Returns the
    row count. The table also enables the BigQuery mesh connector's native
    ``FOR SYSTEM_TIME AS OF`` time-travel on data we own. ``client`` is injectable
    (tests / explicit credentials); otherwise built from ADC. Lazy SDK import.
    """
    from google.cloud import bigquery

    table = table or os.environ.get(
        "EZRA_BQ_F1_TABLE",
        f"{settings.bigquery_project or 'ezra-498021'}."
        f"{settings.bigquery_dataset or 'formula_1'}.race_results",
    )
    project = table.split(".")[0]
    dataset_id = ".".join(table.split(".")[:2])
    if client is None:
        client = bigquery.Client(project=project)
    client.create_dataset(bigquery.Dataset(dataset_id), exists_ok=True)

    schema = [
        bigquery.SchemaField("season", "INTEGER"),
        bigquery.SchemaField("round", "INTEGER"),
        bigquery.SchemaField("race_name", "STRING"),
        bigquery.SchemaField("circuit", "STRING"),
        bigquery.SchemaField("date", "STRING"),
        bigquery.SchemaField("position", "STRING"),
        bigquery.SchemaField("driver", "STRING"),
        bigquery.SchemaField("constructor", "STRING"),
        bigquery.SchemaField("grid", "STRING"),
        bigquery.SchemaField("status", "STRING"),
        bigquery.SchemaField("points", "STRING"),
    ]
    keys = [f.name for f in schema]
    job_config = bigquery.LoadJobConfig(
        schema=schema, write_disposition="WRITE_TRUNCATE"
    )
    payload = [{k: r.get(k) for k in keys} for r in rows]
    client.load_table_from_json(payload, table, job_config=job_config).result()
    return len(payload)


async def _main() -> None:  # pragma: no cover - script entry point
    from pymongo import AsyncMongoClient

    from ezra_core.atlas_access import ensure_egress_allowed
    from ezra_core.config import EzraSettings
    from ezra_core.secret_files import load_secret_files

    load_secret_files()  # GKE: pull Atlas URI from the Secret Manager CSI mount
    settings = EzraSettings()
    if not settings.mongodb_uri:
        raise SystemExit("EZRA_MONGODB_URI is not set — cannot ingest to Atlas.")
    ensure_egress_allowed(settings)  # allow this job's egress IP on Atlas (no-op locally)

    # On GKE these are on by default; locally they need the `ingest` deps + auth,
    # so allow opting out via env.
    include_bigquery = os.environ.get("EZRA_INGEST_BIGQUERY", "true").lower() == "true"
    include_fastf1 = os.environ.get("EZRA_INGEST_FASTF1", "true").lower() == "true"
    project = os.environ.get("EZRA_GCP_PROJECT_ID", "")

    # Wide mode = the full historical spine across a season range (default 1950→last
    # complete season). Set EZRA_INGEST_WIDE=false for the light single-weekend corpus.
    wide = os.environ.get("EZRA_INGEST_WIDE", "true").lower() == "true"
    season_start = int(os.environ.get("EZRA_INGEST_SEASON_START", "1950"))
    season_end = int(os.environ.get("EZRA_INGEST_SEASON_END", "2025"))
    # Higher delay stays under Jolpica's ~500/hr unauthenticated limit → fewer 429s
    # and a more complete pull (at the cost of wall time). Tune per run.
    polite_delay = float(os.environ.get("EZRA_INGEST_POLITE_DELAY", "0.3"))
    include_openf1 = os.environ.get("EZRA_INGEST_OPENF1", "true").lower() == "true"
    include_enterprise = os.environ.get("EZRA_INGEST_ENTERPRISE", "true").lower() == "true"
    enterprise_start = int(os.environ.get("EZRA_ENTERPRISE_START_SEASON", "2010"))

    if wide:
        seasons = range(season_start, season_end + 1)
        print(f"Fetching WIDE F1 corpus: seasons {season_start}–{season_end} "
              f"(delay={polite_delay}s)"
              f"{' + OpenF1' if include_openf1 else ''}"
              f"{' + enterprise' if include_enterprise else ''}"
              f"{' + BigQuery' if include_bigquery else ''}"
              f"{' + FastF1' if include_fastf1 else ''} (this takes a while)…")
        dataset = await build_wide_dataset(
            seasons=seasons,
            polite_delay=polite_delay,
            include_openf1=include_openf1,
            include_enterprise=include_enterprise,
            enterprise_start_season=enterprise_start,
            include_bigquery=include_bigquery,
            include_fastf1=include_fastf1,
            bq_project=project,
        )
    else:
        print(f"Fetching F1 data (Jolpica + OpenF1"
              f"{' + BigQuery' if include_bigquery else ''}"
              f"{' + FastF1' if include_fastf1 else ''})…")
        dataset = await build_live_dataset(
            include_bigquery=include_bigquery, include_fastf1=include_fastf1, bq_project=project
        )

    ensure_egress_allowed(settings)  # re-assert just before connecting (long fetch may have elapsed)
    client = AsyncMongoClient(settings.mongodb_uri)
    counts = await ingest_to_mongo(client, settings.mongodb_db, dataset=dataset)
    total = sum(counts.values())
    for name, n in counts.items():
        print(f"  {name}: {n}")
    print(f"Done (MongoDB). {total} rows across {len(counts)} collections.")

    # Distribute domain-appropriate slices across the three federated stores so each
    # source is distinct and each agent's connector returns its own domain:
    #   Snowflake = historical results + standings (time-travel warehouse)
    #   BigQuery  = aero / car-setup / R&D analytics (engineering warehouse)
    #   MongoDB   = everything operational + telemetry + private systems (above)
    results = dataset.get("race_results", [])
    bq_project = settings.bigquery_project or "ezra-498021"
    bq_dataset = settings.bigquery_dataset or "formula_1"

    if os.environ.get("EZRA_INGEST_SNOWFLAKE", "true").lower() == "true" \
            and settings.snowflake_account:
        try:
            n = await asyncio.to_thread(load_results_to_snowflake, settings, results)
            print(f"Done (Snowflake RACE_RESULTS). {n} rows.")
            for tbl in ("driver_standings", "constructor_standings"):
                rows = dataset.get(tbl, [])
                if rows:
                    m = await asyncio.to_thread(load_table_to_snowflake, settings, tbl, rows)
                    print(f"Done (Snowflake {tbl.upper()}). {m} rows.")
        except Exception as exc:
            print(f"WARN snowflake load failed: {exc}")

    if include_bigquery:
        for tbl in ("aero_configs", "car_setups", "rd_experiments"):
            rows = dataset.get(tbl, [])
            if not rows:
                continue
            try:
                n = await asyncio.to_thread(
                    load_table_to_bigquery, settings, f"{bq_project}.{bq_dataset}.{tbl}", rows
                )
                print(f"Done (BigQuery {tbl}). {n} rows.")
            except Exception as exc:
                print(f"WARN bigquery {tbl} load failed: {exc}")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(_main())
