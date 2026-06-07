"""Exceptions raised by the Ezra client."""

from __future__ import annotations

from typing import Iterable


class PolicyDeniedError(PermissionError):
    """Raised when an agent accesses a topic outside its permission scope.

    Mirrors ``ezra_core.policy.engine.PolicyDeniedError`` — the remote service
    returns HTTP 403 for a scope denial, and the client re-raises it as this so
    caller code catches the same type whether Ezra runs in-process or remote.
    """

    def __init__(self, topic: str, scope: Iterable[str]) -> None:
        self.topic = topic
        self.scope = list(scope)
        super().__init__(f"topic {topic!r} not in agent scope {self.scope}")


class RemoteEzraError(RuntimeError):
    """A non-policy error returned by the remote Ezra service."""
