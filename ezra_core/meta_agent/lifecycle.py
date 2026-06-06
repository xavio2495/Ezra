"""Lifecycle meta-agent — runs on a schedule (5 min / active graph, 1 hr /
closed graph), asynchronous and non-blocking.

Jobs (HANDOFF "Two meta-agents"):

  - **active → closed** when the last agent terminates.
  - **closed → archived** after the graph's ``archival_threshold_days`` of idle.
  - **archival compaction** — drop warm summaries past TTL (belief history is
    retained verbatim; semantic is the learning agent's domain).
  - **belief-retention TTL** — tombstone commitments older than the graph's
    ``belief_retention_days`` (``None`` = infinite, the default).
  - **GDPR tombstones** — apply a redaction tombstone on request.

Per-graph configuration is read off the ``SessionGraph`` record itself
(``archival_threshold_days`` / ``belief_retention_days``), so one agent serves
graphs with different retention policies. State transitions go through the same
``SessionGraphStore`` the runtime uses; tombstones/compaction reuse the belief
store's ``redact`` and the warm tier's ``evict_expired`` — no new ports.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import BaseModel, Field

from ezra_core.belief.store import BeliefStore
from ezra_core.observability.tracer import EzraTracer
from ezra_core.schemas.session_graph import SessionGraphState
from ezra_core.session_graph import SessionGraphStore
from ezra_core.tiers.warm import WarmTier


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LifecycleReport(BaseModel):
    """What one scheduled lifecycle pass did (for the dashboard / tracer)."""

    session_graph_id: str
    transition: Optional[str] = None  # "closed" | "archived" | None
    evicted_warm: bool = False
    tombstoned_commitment_ids: list[str] = Field(default_factory=list)


class LifecycleMetaAgent:
    def __init__(
        self,
        store: SessionGraphStore,
        *,
        belief_store: Optional[BeliefStore] = None,
        warm: Optional[WarmTier] = None,
        tracer: Optional[EzraTracer] = None,
    ) -> None:
        self._store = store
        self._belief = belief_store
        self._warm = warm
        # Owns the `meta.lifecycle` span for its scheduled pass.
        self._tracer = tracer or EzraTracer.disabled()

    # -- state transitions ------------------------------------------------ #
    async def close_if_idle(
        self, session_graph_id: str, *, now: Optional[datetime] = None
    ) -> bool:
        """active → closed once no agents remain active."""
        record = await self._store.get(session_graph_id)
        if record is None:
            return False
        if record.state == SessionGraphState.ACTIVE and not record.active_agents:
            record.state = SessionGraphState.CLOSED
            record.closed_at = now or _utcnow()
            await self._store.save(record)
            return True
        return False

    async def archive_if_stale(
        self, session_graph_id: str, *, now: Optional[datetime] = None
    ) -> bool:
        """closed → archived once idle past the graph's archival threshold."""
        record = await self._store.get(session_graph_id)
        if record is None or record.state != SessionGraphState.CLOSED:
            return False
        if record.closed_at is None:
            return False
        now = now or _utcnow()
        if (now - record.closed_at) >= timedelta(days=record.archival_threshold_days):
            record.state = SessionGraphState.ARCHIVED
            record.archived_at = now
            await self._store.save(record)
            return True
        return False

    # -- compaction / TTL ------------------------------------------------- #
    async def compact_warm(self, *, now: Optional[datetime] = None) -> bool:
        if self._warm is None:
            return False
        await self._warm.evict_expired(now=now)
        return True

    async def enforce_belief_retention(
        self, session_graph_id: str, *, now: Optional[datetime] = None
    ) -> list[str]:
        """Tombstone commitments older than the graph's belief_retention_days."""
        if self._belief is None:
            return []
        record = await self._store.get(session_graph_id)
        if record is None or record.belief_retention_days is None:
            return []
        now = now or _utcnow()
        cutoff = now - timedelta(days=record.belief_retention_days)
        tombstoned: list[str] = []
        for c in await self._belief.get_all(session_graph_id):
            if not c.redacted and c.created_at < cutoff:
                await self._belief.redact(c.id, "belief_retention_ttl")
                tombstoned.append(c.id)
        return tombstoned

    # -- GDPR ------------------------------------------------------------- #
    async def apply_tombstone(self, commitment_id: str, reason: str) -> None:
        if self._belief is not None:
            await self._belief.redact(commitment_id, reason)

    # -- scheduled pass --------------------------------------------------- #
    async def tick(
        self, session_graph_id: str, *, now: Optional[datetime] = None
    ) -> LifecycleReport:
        now = now or _utcnow()
        with self._tracer.span(
            "meta.lifecycle", session_graph_id=session_graph_id
        ) as span:
            report = LifecycleReport(session_graph_id=session_graph_id)
            if await self.close_if_idle(session_graph_id, now=now):
                report.transition = "closed"
            elif await self.archive_if_stale(session_graph_id, now=now):
                report.transition = "archived"
            report.tombstoned_commitment_ids = await self.enforce_belief_retention(
                session_graph_id, now=now
            )
            report.evicted_warm = await self.compact_warm(now=now)
            span.set_attributes(
                {
                    "meta.transition": report.transition or "none",
                    "meta.tombstoned_count": len(report.tombstoned_commitment_ids),
                    "meta.evicted_warm": report.evicted_warm,
                }
            )
            return report
