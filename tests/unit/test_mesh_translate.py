"""NL→native query translation + the allowlist/keyword-reject safety layer.

The validation functions are the whole defense against LLM-generated SQL, so they
get focused coverage: allowlisted predicates compose correctly; injection / DDL /
cross-column / $where attempts fall back to the safe query.
"""

from datetime import datetime, timezone

from ezra_core.mesh.bigquery import BigQueryConnector
from ezra_core.mesh.mongodb_mcp import MongoMcpConnector
from ezra_core.mesh.snowflake import SnowflakeConnector
from ezra_core.mesh.translate import (
    NoopTranslator,
    SqlPredicate,
    compose_select,
    validate_mongo_filter,
    validate_sql_predicate,
)

COLS = {"season": "int", "circuit": "str", "winner": "str"}


# -- SQL predicate validation --------------------------------------------- #
def test_valid_predicate_kept():
    p = validate_sql_predicate(
        projection=["winner", "season"], where="season = 2023 and circuit = 'Monaco'",
        limit=10, columns=COLS,
    )
    assert p.projection == ["winner", "season"]
    assert p.where == "season = 2023 and circuit = 'Monaco'"
    assert p.limit == 10


def test_unknown_column_in_projection_dropped():
    p = validate_sql_predicate(projection=["winner", "salary"], where="", limit=5, columns=COLS)
    assert p.projection == ["winner"]  # 'salary' not allowlisted


def test_where_referencing_unknown_column_rejected():
    p = validate_sql_predicate(projection=["*"], where="salary > 100", limit=5, columns=COLS)
    assert p.where == ""  # whole predicate dropped → safe


def test_injection_and_ddl_rejected():
    for bad in [
        "season = 2023; DROP TABLE results",
        "1=1 UNION SELECT * FROM secrets",
        "season = 2023 -- comment",
        "season = (SELECT max(season) FROM other)",
    ]:
        p = validate_sql_predicate(projection=["*"], where=bad, limit=5, columns=COLS)
        assert p.where == "", bad


def test_limit_clamped():
    assert validate_sql_predicate(projection=["*"], where="", limit=99999, columns=COLS).limit == 1000
    assert validate_sql_predicate(projection=["*"], where="", limit=0, columns=COLS).limit == 1
    assert validate_sql_predicate(projection=["*"], where="", limit="x", columns=COLS).limit == 100


def test_compose_select_uses_validated_slots_and_table():
    pred = SqlPredicate(projection=["winner"], where="season = 2023", limit=5)
    sql = compose_select("EZRA.PUBLIC.RACE_RESULTS", pred, time_travel="AT (TIMESTAMP => 't')")
    assert sql == "SELECT winner FROM EZRA.PUBLIC.RACE_RESULTS AT (TIMESTAMP => 't') WHERE season = 2023 LIMIT 5"


# -- Mongo filter validation ---------------------------------------------- #
def test_mongo_allowlisted_filter_kept():
    f = validate_mongo_filter({"season": 2023, "winner": {"$in": ["VER", "LEC"]}}, columns=COLS)
    assert f == {"season": 2023, "winner": {"$in": ["VER", "LEC"]}}


def test_mongo_unknown_field_discards_whole_filter():
    assert validate_mongo_filter({"season": 2023, "salary": {"$gt": 1}}, columns=COLS) == {}


def test_mongo_dangerous_operator_rejected():
    assert validate_mongo_filter({"$where": "this.x"}, columns=COLS) == {}
    assert validate_mongo_filter({"season": {"$function": {}}}, columns=COLS) == {}


# -- Connector integration (fake translator) ------------------------------ #
class FakeTranslator:
    def __init__(self, predicate=None, mongo=None):
        self._p = predicate or SqlPredicate(["winner"], "season = 2023", 10)
        self._m = mongo if mongo is not None else {"season": 2023}

    def to_sql(self, intent, *, columns):
        return self._p

    def to_mongo_filter(self, intent, *, columns):
        return self._m


def test_snowflake_uses_translator_when_columns_set():
    conn = SnowflakeConnector("T", columns=COLS, translator=FakeTranslator())
    assert conn.build_sql("who won 2023?") == "SELECT winner FROM T WHERE season = 2023 LIMIT 10"


def test_snowflake_falls_back_to_select_star_without_translator():
    conn = SnowflakeConnector("T")
    assert conn.build_sql("anything") == "SELECT * FROM T"


def test_bigquery_backticks_table_with_translation():
    conn = BigQueryConnector("p.d.t", columns=COLS, translator=FakeTranslator())
    assert conn.build_sql("q") == "SELECT winner FROM `p.d.t` WHERE season = 2023 LIMIT 10"


async def test_mongo_connector_translates_nl_to_filter():
    captured = {}

    class _Cursor:
        def limit(self, n):
            return self

        def __aiter__(self):
            async def gen():
                if False:
                    yield {}
            return gen()

    class _Coll:
        def find(self, filt):
            captured["filter"] = filt
            return _Cursor()

    conn = MongoMcpConnector(
        _Coll(), columns=COLS, translator=FakeTranslator(mongo={"season": 2023})
    )
    await conn.fetch("who won in 2023?", "agent", ["telemetry"])
    assert captured["filter"] == {"season": 2023}


def test_noop_translator_is_passthrough():
    nt = NoopTranslator()
    assert nt.to_sql("x", columns=COLS) == SqlPredicate(["*"], "", 100)
    assert nt.to_mongo_filter("x", columns=COLS) == {}
