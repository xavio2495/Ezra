import httpx

from demo.f1_race_weekend.data_ingestion import (
    build_dataset,
    build_live_dataset,
    fetch_bigquery_f1,
    fetch_fastf1_session,
    fetch_jolpica_results,
)


class _FakeBQResult:
    def __init__(self, rows):
        self._rows = rows

    def result(self):
        return self._rows


class _FakeBQClient:
    def __init__(self, rows):
        self._rows = rows
        self.last_query = None

    def query(self, query, job_config=None):
        self.last_query = query
        return _FakeBQResult(self._rows)


def _fastf1_loader(year, event, session_type, cache_dir):
    return [{"Abbreviation": "LEC", "TeamName": "Ferrari", "Position": 1.0,
             "Points": 25.0, "Status": "Finished"}]

_RESULTS = {"MRData": {"RaceTable": {"Races": [{
    "round": "8", "Circuit": {"circuitName": "Circuit de Monaco"},
    "Results": [{
        "position": "1", "points": "25", "grid": "1", "status": "Finished",
        "Driver": {"code": "LEC", "familyName": "Leclerc"},
        "Constructor": {"name": "Ferrari"}, "Time": {"time": "2:23:15.554"},
    }],
}]}}}
_SCHEDULE = {"MRData": {"RaceTable": {"Races": [{
    "round": "8", "raceName": "Monaco Grand Prix",
    "Circuit": {"circuitName": "Circuit de Monaco"}, "date": "2024-05-26",
}]}}}
_QUALI = {"MRData": {"RaceTable": {"Races": [{
    "Circuit": {"circuitName": "Circuit de Monaco"},
    "QualifyingResults": [{
        "position": "1", "Driver": {"code": "LEC"},
        "Constructor": {"name": "Ferrari"}, "Q1": "1:11", "Q2": "1:10", "Q3": "1:10.270",
    }],
}]}}}
_SESSIONS = [{"session_key": 9999, "session_name": "Race",
              "date_start": "2024-05-26T13:00:00", "circuit_short_name": "Monaco"}]
_WEATHER = [{"date": "2024-05-26T13:00:00", "air_temperature": 24.5,
             "track_temperature": 40.1, "rainfall": 0, "humidity": 50, "wind_speed": 2.1}]


def _handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "results.json" in url:
        return httpx.Response(200, json=_RESULTS)
    if "qualifying.json" in url:
        return httpx.Response(200, json=_QUALI)
    if url.rstrip("/").endswith("/2024.json"):
        return httpx.Response(200, json=_SCHEDULE)
    if "openf1.org/v1/sessions" in url:
        return httpx.Response(200, json=_SESSIONS)
    if "openf1.org/v1/weather" in url:
        return httpx.Response(200, json=_WEATHER)
    return httpx.Response(404, json={})


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(_handler))


def test_build_dataset_offline_unchanged():
    data = build_dataset()
    assert set(data) >= {"parts_inventory", "rd_experiments", "supplier_contracts", "race_results"}


async def test_fetch_jolpica_results_parses_ergast():
    async with _client() as c:
        rows = await fetch_jolpica_results(c, season=2024)
    assert rows[0]["driver"] == "LEC"
    assert rows[0]["constructor"] == "Ferrari"
    assert rows[0]["position"] == "1"
    assert rows[0]["topics"] == ["strategy"]


async def test_build_live_dataset_assembles_all_collections():
    async with _client() as c:
        data = await build_live_dataset(season=2024, year=2024, client=c)

    assert data["race_results"][0]["driver"] == "LEC"
    assert data["race_calendar"][0]["race_name"] == "Monaco Grand Prix"
    assert data["qualifying"][0]["driver"] == "LEC"
    assert data["sessions"][0]["session_name"] == "Race"
    # Weather was fetched using the Race session's key.
    assert data["weather"][0]["track_temperature"] == 40.1
    # Synthesised team systems are merged in too.
    assert data["parts_inventory"]


def test_fetch_bigquery_f1_maps_rows():
    rows = [{"season": 2023, "round": 7, "circuit": "Circuit de Monaco",
             "driver": "VER", "constructor": "Red Bull", "position": "1", "points": 25}]
    client = _FakeBQClient(rows)
    out = fetch_bigquery_f1(client)
    assert out[0]["driver"] == "VER"
    assert out[0]["season"] == 2023
    assert out[0]["constructor"] == "Red Bull"
    assert out[0]["topics"] == ["strategy"]


def test_fetch_fastf1_session_maps_results():
    out = fetch_fastf1_session(_fastf1_loader, year=2024)
    assert out[0]["driver"] == "LEC"
    assert out[0]["team"] == "Ferrari"
    assert out[0]["session"] == "R"
    assert "telemetry" in out[0]["topics"]


async def test_build_live_dataset_includes_heavy_sources_when_enabled():
    async with _client() as c:
        data = await build_live_dataset(
            season=2024, year=2024, client=c,
            include_bigquery=True, bq_client=_FakeBQClient(
                [{"season": 2023, "round": 7, "circuit": "Monaco", "driver": "VER",
                  "constructor": "Red Bull", "position": "1", "points": 25}]),
            include_fastf1=True, fastf1_loader=_fastf1_loader,
        )
    assert data["historical_results"][0]["driver"] == "VER"
    assert data["session_timing"][0]["driver"] == "LEC"
