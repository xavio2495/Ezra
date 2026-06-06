"""NL → native query translation for the federated mesh.

A connector turns an agent's natural-language intent into a *native* pushdown
query. The query is produced by an LLM, so it is NEVER executed as free-form SQL:
the connector keeps ownership of the table (``FROM``) and the time-travel clause,
and the translator only fills **validated slots** — a projection (⊆ allowlisted
columns), a WHERE predicate (referencing only allowlisted columns, read-only),
and a row limit. Anything that fails validation falls back to the safe
``SELECT * … LIMIT n`` / unfiltered find. This is the whole defense against
LLM-generated SQL and must not be weakened.

``QueryTranslator`` is a Protocol so connectors stay testable with fakes;
``LLMQueryTranslator`` is the real Gemini-backed implementation (same structured-
JSON pattern as ``GeminiNliClassifier`` in ``llm/adapter.py``). ``NoopTranslator``
is the passthrough default (keeps ``SELECT *`` behaviour).
"""

from __future__ import annotations

import json
import re
from typing import Any, NamedTuple, Optional, Protocol

# Keywords / tokens that must never appear in a generated predicate — any hit
# means we discard the predicate and fall back to the safe query.
_FORBIDDEN = re.compile(
    r"(;|--|/\*|\*/|\b(insert|update|delete|drop|alter|create|merge|grant|"
    r"revoke|truncate|union|exec|execute|call|into|attach)\b)",
    re.IGNORECASE,
)
# Single-quoted string literals (their contents are values, not identifiers).
_STRLIT = re.compile(r"'(?:[^']|'')*'")
# Identifiers referenced in a predicate (bare column names), after literals removed.
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# SQL keywords/operators allowed to appear as bare words alongside identifiers.
_SQL_WORDS = {
    "and", "or", "not", "in", "is", "null", "between", "like", "true", "false",
    "asc", "desc",
}
# Mongo filter operators we permit (no $where / $function / $expr / $accumulator).
_SAFE_MONGO_OPS = {"$eq", "$ne", "$gt", "$gte", "$lt", "$lte", "$in", "$nin", "$and", "$or"}


class SqlPredicate(NamedTuple):
    """A validated, composable SQL predicate. ``projection`` is a column list (or
    ``["*"]``); ``where`` is a bare boolean expression (no ``WHERE`` keyword) or
    empty; ``limit`` caps rows."""

    projection: list[str]
    where: str
    limit: int


class QueryTranslator(Protocol):
    def to_sql(self, intent: str, *, columns: dict[str, str]) -> SqlPredicate: ...
    def to_mongo_filter(self, intent: str, *, columns: dict[str, str]) -> dict: ...


# --------------------------------------------------------------------------- #
# Validation (the load-bearing safety layer — pure, unit-tested)
# --------------------------------------------------------------------------- #
def validate_sql_predicate(
    *,
    projection: Any,
    where: Any,
    limit: Any,
    columns: dict[str, str],
    default_limit: int = 100,
    max_limit: int = 1000,
) -> SqlPredicate:
    """Coerce + validate translated slots into a safe ``SqlPredicate``. Returns
    the safe fallback (``SELECT *``) on anything suspect — never raises."""
    allowed = {c.lower() for c in columns}

    # Projection: keep only allowlisted columns; empty/invalid → ["*"].
    proj: list[str] = []
    if isinstance(projection, list):
        for col in projection:
            if isinstance(col, str) and col.lower() in allowed:
                proj.append(col)
    proj = proj or ["*"]

    # WHERE: reject forbidden tokens; every identifier must be an allowed column
    # or a permitted SQL word.
    safe_where = ""
    if isinstance(where, str) and where.strip():
        candidate = where.strip()
        if not _FORBIDDEN.search(candidate):
            # Strip string literals first — 'Monaco' is a value, not a column.
            without_literals = _STRLIT.sub("", candidate)
            idents = _IDENT.findall(without_literals)
            if all(
                tok.lower() in allowed or tok.lower() in _SQL_WORDS for tok in idents
            ):
                safe_where = candidate

    # Limit: clamp to [1, max_limit].
    try:
        lim = int(limit)
    except (TypeError, ValueError):
        lim = default_limit
    lim = max(1, min(lim, max_limit))

    return SqlPredicate(projection=proj, where=safe_where, limit=lim)


def validate_mongo_filter(filt: Any, *, columns: dict[str, str]) -> dict:
    """Validate a translated Mongo filter: keys ⊆ allowlist (or a safe logical
    operator), operators ⊆ the safe set, values scalar/list. Returns ``{}`` (find-
    all) on anything suspect."""
    allowed = {c.lower() for c in columns}

    def _ok_value(v: Any) -> bool:
        if isinstance(v, dict):
            return all(
                k in _SAFE_MONGO_OPS and _ok_value(sub) for k, sub in v.items()
            )
        if isinstance(v, list):
            return all(_ok_value(x) for x in v)
        return isinstance(v, (str, int, float, bool)) or v is None

    if not isinstance(filt, dict):
        return {}
    out: dict = {}
    for key, value in filt.items():
        if key in ("$and", "$or"):
            if isinstance(value, list) and all(
                isinstance(c, dict) and validate_mongo_filter(c, columns=columns) == c
                for c in value
            ):
                out[key] = value
            else:
                return {}
        elif key.lower() in allowed and _ok_value(value):
            out[key] = value
        else:
            return {}  # any unknown field/operator → discard the whole filter
    return out


def compose_select(table: str, pred: SqlPredicate, *, time_travel: str = "") -> str:
    """Compose the final SQL from a validated predicate. The connector owns
    ``table`` + ``time_travel``; only the validated slots come from the LLM."""
    cols = ", ".join(pred.projection)
    tt = f" {time_travel}" if time_travel else ""
    where = f" WHERE {pred.where}" if pred.where else ""
    return f"SELECT {cols} FROM {table}{tt}{where} LIMIT {pred.limit}"


def _parse_json_object(text: str) -> dict:
    """Parse an LLM reply into a dict, tolerating ```-fenced JSON."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


# --------------------------------------------------------------------------- #
# Implementations
# --------------------------------------------------------------------------- #
class NoopTranslator:
    """Passthrough: no translation. SQL → ``SELECT *``; Mongo → find-all."""

    def to_sql(self, intent: str, *, columns: dict[str, str]) -> SqlPredicate:
        return SqlPredicate(projection=["*"], where="", limit=100)

    def to_mongo_filter(self, intent: str, *, columns: dict[str, str]) -> dict:
        return {}


class LLMQueryTranslator:
    """Gemini-backed NL→native translator. Returns only validated slots; the
    connector composes the final query. Any model/parse/validation failure
    degrades to the safe fallback (never raises into the connector)."""

    def __init__(self, model: str = "gemini/gemini-3.5-flash", *, api_key: Optional[str] = None):
        self._model = model
        self._api_key = api_key

    def _ask(self, prompt: str) -> dict:
        import litellm

        try:
            resp = litellm.completion(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                api_key=self._api_key,
                temperature=0.0,
            )
            return _parse_json_object(resp.choices[0].message.content)
        except Exception:  # noqa: BLE001 — translation is best-effort; fall back safe
            return {}

    def to_sql(self, intent: str, *, columns: dict[str, str]) -> SqlPredicate:
        cols = ", ".join(f"{n} ({t})" for n, t in columns.items())
        prompt = (
            "Translate the request into a READ-ONLY SQL filter over a single table. "
            "Respond ONLY with compact JSON: "
            '{"projection": [col, ...], "where": "<bool expr, no WHERE keyword>", '
            '"limit": <int>}. Use ONLY these columns; reference no other table; no '
            "subqueries, no semicolons, no DDL/DML. Empty where means no filter.\n\n"
            f"Columns: {cols}\nRequest: {intent}"
        )
        data = self._ask(prompt)
        return validate_sql_predicate(
            projection=data.get("projection"),
            where=data.get("where"),
            limit=data.get("limit"),
            columns=columns,
        )

    def to_mongo_filter(self, intent: str, *, columns: dict[str, str]) -> dict:
        cols = ", ".join(f"{n} ({t})" for n, t in columns.items())
        prompt = (
            "Translate the request into a READ-ONLY MongoDB find filter. Respond "
            "ONLY with compact JSON: the filter object. Use ONLY these fields and "
            "the operators $eq,$ne,$gt,$gte,$lt,$lte,$in,$nin,$and,$or. No $where, "
            "$function, $expr. Empty object means match all.\n\n"
            f"Fields: {cols}\nRequest: {intent}"
        )
        return validate_mongo_filter(self._ask(prompt), columns=columns)


def translator_from_settings(settings) -> LLMQueryTranslator:
    """Build the production translator (Gemini via the meta model, which is cheap
    and structured-JSON friendly). Vertex models authenticate via ADC (no key)."""
    from ezra_core.llm.adapter import is_vertex_model

    key = None if is_vertex_model(settings.meta_agent_model) else (settings.llm_api_key or None)
    return LLMQueryTranslator(settings.meta_agent_model, api_key=key)
