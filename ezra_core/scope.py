"""Permission-scope filtering, shared by the memory stores and the router.

An item is visible to a scope if it is untopiced (applies everywhere) or shares
at least one topic with the scope. Matches the HANDOFF ``filter_by_scope``.
"""

from __future__ import annotations

from typing import Iterable, Protocol, TypeVar


class _HasTopics(Protocol):
    topics: list[str]


def matches_scope(topics: list[str], scope_topics: set[str]) -> bool:
    return not topics or bool(set(topics) & scope_topics)


T = TypeVar("T", bound=_HasTopics)


def filter_by_scope(items: Iterable[T], scope_topics: set[str]) -> list[T]:
    return [item for item in items if matches_scope(item.topics, scope_topics)]
