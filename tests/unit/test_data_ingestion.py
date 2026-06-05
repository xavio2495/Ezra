import httpx

from demo.f1_race_weekend.data_ingestion import (
    build_dataset,
    build_live_dataset,
    build_wide_dataset,
    fetch_bigquery_f1,
    fetch_constructor_standings,
    fetch_driver_standings,
    fetch_fastf1_session,
    fetch_jolpica_results,
    fetch_season_results,
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


# -- wide historical spine ------------------------------------------------- #
def _season_results_page(total: int, races: list[dict]) -> dict:
    return {"MRData": {"total": str(total), "RaceTable": {"Races": races}}}


_RACE_A = {"round": "1", "raceName": "Bahrain GP", "Circuit": {"circuitName": "Bahrain"},
           "date": "2023-03-05", "Results": [
               {"position": "1", "points": "25", "grid": "1", "status": "Finished",
                "Driver": {"code": "VER"}, "Constructor": {"name": "Red Bull"}}]}
_RACE_B = {"round": "2", "raceName": "Saudi GP", "Circuit": {"circuitName": "Jeddah"},
           "date": "2023-03-19", "Results": [
               {"position": "1", "points": "25", "grid": "2", "status": "Finished",
                "Driver": {"code": "PER"}, "Constructor": {"name": "Red Bull"}}]}
_DRIVER_STANDINGS = {"MRData": {"StandingsTable": {"StandingsLists": [
    {"DriverStandings": [{"position": "1", "points": "575", "wins": "19",
                          "Driver": {"code": "VER"},
                          "Constructors": [{"name": "Red Bull"}]}]}]}}}
_CONSTRUCTOR_STANDINGS = {"MRData": {"StandingsTable": {"StandingsLists": [
    {"ConstructorStandings": [{"position": "1", "points": "860", "wins": "21",
                               "Constructor": {"name": "Red Bull"}}]}]}}}
_CIRCUITS = {"MRData": {"total": "2", "CircuitTable": {"Circuits": [
    {"circuitId": "monaco", "circuitName": "Circuit de Monaco",
     "Location": {"locality": "Monte-Carlo", "country": "Monaco", "lat": "43.7", "long": "7.4"}},
    {"circuitId": "silverstone", "circuitName": "Silverstone",
     "Location": {"locality": "Silverstone", "country": "UK", "lat": "52.0", "long": "-1.0"}}]}}}


def _wide_handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "/results.json" in url:
        return httpx.Response(200, json=_season_results_page(2, [_RACE_A, _RACE_B]))
    if "/driverStandings.json" in url:
        return httpx.Response(200, json=_DRIVER_STANDINGS)
    if "/constructorStandings.json" in url:
        return httpx.Response(200, json=_CONSTRUCTOR_STANDINGS)
    if "/circuits.json" in url:
        return httpx.Response(200, json=_CIRCUITS)
    return httpx.Response(404, json={})


def _wide_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(_wide_handler))


async def test_fetch_season_results_flattens_all_rounds():
    async with _wide_client() as c:
        rows = await fetch_season_results(c, season=2023, polite_delay=0.0)
    assert {r["driver"] for r in rows} == {"VER", "PER"}
    assert all(r["season"] == 2023 for r in rows)
    assert {r["round"] for r in rows} == {1, 2}


async def test_fetch_standings_parse():
    async with _wide_client() as c:
        ds = await fetch_driver_standings(c, season=2023)
        cs = await fetch_constructor_standings(c, season=2023)
    assert ds[0]["driver"] == "VER" and ds[0]["wins"] == "19"
    assert cs[0]["constructor"] == "Red Bull" and cs[0]["points"] == "860"


async def test_build_wide_dataset_spans_seasons():
    async with _wide_client() as c:
        data = await build_wide_dataset(
            seasons=range(2022, 2024), client=c, polite_delay=0.0
        )
    # Two seasons × two rounds = four result rows.
    assert len(data["race_results"]) == 4
    assert len(data["driver_standings"]) == 2  # one per season
    assert {ci["circuit_id"] for ci in data["circuits"]} == {"monaco", "silverstone"}
    assert data["parts_inventory"]  # synthesised systems merged in
