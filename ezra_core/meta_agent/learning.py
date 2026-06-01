"""Learning meta-agent — runs after router step 8, every turn, non-blocking.

Three jobs (HANDOFF "Two meta-agents"):

  1. **Memory write scoring** — of the facts extracted from a turn, only those
     confident enough deserve cold persistence. Low-confidence candidates are
     dropped rather than polluting semantic memory.
  2. **Core/archival promotion** — an archival fact accessed often enough
     (``core_promotion_access_count``, default 3) graduates to ``core`` so it
     loads at every agent spawn instead of only on similarity match.
  3. **Trust updates** — after a reconciliation, the winning/losing agent's
     per-topic trust moves toward 1.0 / 0.0, *damped* so a single event nudges
     rather than swings it.

Pure logic over the existing ``SemanticStore`` — no new persistence port, no LLM
call (fact extraction itself is the caller's/agent's job; this scores what it is
handed). Methods are individually callable; ``run_after_turn`` orchestrates them
and returns a ``LearningReport`` for the dashboard / tracer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence

from pydantic import BaseModel, Field

from ezra_core.memory.semantic import SemanticStore
from ezra_core.schemas.memory import SemanticFact
from ezra_core.schemas.session_graph import AgentRegistration


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LearningReport(BaseModel):
    """What the learning pass did this turn (surfaced to dashboard / Phoenix)."""

    persisted_fact_ids: list[str] = Field(default_factory=list)
    promoted_fact_ids: list[str] = Field(default_factory=list)
    trust_updates: dict[str, float] = Field(default_factory=dict)  # "agent:topic" -> new


class LearningMetaAgent:
    def __init__(
        self,
        semantic_store: SemanticStore,
        *,
        promotion_access_count: int = 3,
        write_confidence_threshold: float = 0.5,
        trust_damping: float = 0.2,
    ) -> None:
        self._semantic = semantic_store
        self._promotion_access_count = promotion_access_count
        self._write_threshold = write_confidence_threshold
        self._damping = trust_damping

    # -- 1. write scoring ------------------------------------------------- #
    def score_writes(self, candidates: Sequence[SemanticFact]) -> list[SemanticFact]:
        """Keep only candidates confident enough to persist to cold memory."""
        return [f for f in candidates if f.confidence >= self._write_threshold]

    async def persist_writes(self, candidates: Sequence[SemanticFact]) -> list[str]:
        kept = self.score_writes(candidates)
        for fact in kept:
            await self._semantic.add(fact)
        return [f.id for f in kept]

    # -- 2. core/archival promotion -------------------------------------- #
    async def promote_eligible(
        self, *, user_id: str, scope_topics: set[str], source_graph_ids: list[str]
    ) -> list[str]:
        """Promote archival facts whose access count has reached the threshold."""
        archival = await self._semantic.get_archival(
            user_id=user_id,
            scope_topics=scope_topics,
            source_graph_ids=source_graph_ids,
        )
        promoted: list[str] = []
        for fact in archival:
            if fact.access_count >= self._promotion_access_count:
                fact.tier = "core"
                fact.updated_at = _utcnow()
                await self._semantic.add(fact)  # replace_one upsert
                promoted.append(fact.id)
        return promoted

    # -- 3. trust updates ------------------------------------------------- #
    def damp_trust(self, current: float, *, won: bool) -> float:
        """Move ``current`` toward 1.0 (won) or 0.0 (lost), damped by the rate."""
        target = 1.0 if won else 0.0
        return round(current + self._damping * (target - current), 4)

    def record_reconciliation(
        self, registration: AgentRegistration, topic: str, *, won: bool
    ) -> float:
        """Apply a damped trust update for one agent/topic in place; return it."""
        current = registration.trust_scores.get(topic, 1.0)
        updated = self.damp_trust(current, won=won)
        registration.trust_scores[topic] = updated
        return updated

    # -- orchestration ---------------------------------------------------- #
    async def run_after_turn(
        self,
        *,
        user_id: str,
        scope_topics: set[str],
        source_graph_ids: list[str],
        fact_candidates: Sequence[SemanticFact] = (),
        reconciliations: Sequence[tuple[AgentRegistration, str, bool]] = (),
    ) -> LearningReport:
        report = LearningReport()
        report.persisted_fact_ids = await self.persist_writes(fact_candidates)
        report.promoted_fact_ids = await self.promote_eligible(
            user_id=user_id,
            scope_topics=scope_topics,
            source_graph_ids=source_graph_ids,
        )
        for registration, topic, won in reconciliations:
            updated = self.record_reconciliation(registration, topic, won=won)
            report.trust_updates[f"{registration.agent_id}:{topic}"] = updated
        return report
