"""Permission-scope enforcement. A scope is a set of topic tags fixed at agent
spawn. Memory, beliefs, and federated queries are all gated by it.

This is router step 2 (Policy): enforce at the platform layer rather than hoping
the model self-censors. Denials raise ``PolicyDeniedError`` (logged/traced by
the caller).
"""

from __future__ import annotations

from typing import Iterable


class PolicyDeniedError(PermissionError):
    """Raised when an agent accesses a topic outside its permission scope."""

    def __init__(self, topic: str, scope: Iterable[str]) -> None:
        self.topic = topic
        self.scope = list(scope)
        super().__init__(f"topic {topic!r} not in agent scope {self.scope}")


class PolicyEngine:
    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled

    def allows(self, scope: Iterable[str], topic: str) -> bool:
        if not self._enabled:
            return True
        return topic in set(scope)

    def check_topic(self, scope: Iterable[str], topic: str) -> None:
        """Raise PolicyDeniedError if ``topic`` is outside ``scope``."""
        if not self.allows(scope, topic):
            raise PolicyDeniedError(topic, scope)

    def check_topics(self, scope: Iterable[str], topics: Iterable[str]) -> None:
        """Gate a multi-topic access (e.g. a mesh fetch). Denies on the first
        topic outside scope."""
        scope_set = set(scope)
        if not self._enabled:
            return
        for topic in topics:
            if topic not in scope_set:
                raise PolicyDeniedError(topic, scope_set)
