"""Audit event model — a unified, persisted activity feed of what Ezra did.

Ezra already keeps two audit surfaces: OpenTelemetry spans (how a turn was
processed) and the append-only belief log (what was decided). The ``AuditEvent``
log is the third: a single chronological stream maintainers can read to see
*everything an agent did* — spawns, federated fetches, commits, detected
contradictions and how they reconciled, permission denials, reverts/rewinds —
independent of Phoenix and queryable over REST (``GET /ezra/audit``).

Events are written best-effort at the points that already emit spans; an audit
write must never fail the underlying operation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

AuditEventType = Literal[
    "agent_spawned",
    "federated_fetch",
    "fetch_denied",
    "belief_committed",
    "contradiction_detected",
    "contradiction_reconciled",
    "belief_reverted",
    "belief_rewound",
]


class AuditEvent(BaseModel):
    """One thing an agent did, in the session graph's activity feed."""

    id: str
    session_graph_id: str
    agent_id: str
    event_type: AuditEventType
    # The topic this event concerns (empty for events not tied to one topic).
    topic: str = ""
    # Free-form per-event payload (claim, source+rows, winner/loser, strategy …).
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
