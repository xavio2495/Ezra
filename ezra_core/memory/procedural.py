"""Procedural memory — inferred behavioural rules, loaded by scope and (when
inheritance is enabled) from prior graphs via ``source_graph_ids``."""

from __future__ import annotations

from typing import Optional, Protocol

from pymongo import AsyncMongoClient

from ezra_core.schemas.memory import ProceduralRule
from ezra_core.scope import filter_by_scope


def _from_any_graph(rule: ProceduralRule, source_graph_ids: list[str]) -> bool:
    return bool(set(rule.source_session_graph_ids) & set(source_graph_ids))


class ProceduralStore(Protocol):
    async def add(self, rule: ProceduralRule) -> None: ...
    async def get_for_agent(
        self, *, user_id: str, scope_topics: set[str], source_graph_ids: list[str]
    ) -> list[ProceduralRule]: ...


class InMemoryProceduralStore:
    def __init__(self) -> None:
        self._items: dict[str, ProceduralRule] = {}

    async def add(self, rule: ProceduralRule) -> None:
        self._items[rule.id] = rule.model_copy(deep=True)

    async def get_for_agent(
        self, *, user_id: str, scope_topics: set[str], source_graph_ids: list[str]
    ) -> list[ProceduralRule]:
        rules = [
            r.model_copy(deep=True)
            for r in self._items.values()
            if r.user_id == user_id and _from_any_graph(r, source_graph_ids)
        ]
        return filter_by_scope(rules, scope_topics)


def _strip(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


class MongoProceduralStore:
    def __init__(
        self,
        client: AsyncMongoClient,
        db_name: str,
        collection: str = "procedural_rules",
    ) -> None:
        self._c = client[db_name][collection]

    async def add(self, rule: ProceduralRule) -> None:
        doc = rule.model_dump(mode="json")
        doc["_id"] = rule.id
        await self._c.replace_one({"_id": rule.id}, doc, upsert=True)

    async def get_for_agent(
        self, *, user_id: str, scope_topics: set[str], source_graph_ids: list[str]
    ) -> list[ProceduralRule]:
        query = {
            "user_id": user_id,
            "source_session_graph_ids": {"$in": source_graph_ids},
        }
        cursor = self._c.find(query)
        rules = [ProceduralRule.model_validate(_strip(d)) async for d in cursor]
        return filter_by_scope(rules, scope_topics)
