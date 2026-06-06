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

import json
from datetime import datetime, timezone
from typing import Optional, Sequence
from uuid import uuid4

from pydantic import BaseModel, Field

from ezra_core.memory.semantic import SemanticStore
from ezra_core.observability.tracer import EzraTracer
from ezra_core.schemas.memory import SemanticFact
from ezra_core.schemas.session_graph import AgentRegistration


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_json_list(text: str) -> list[dict]:
    """Parse an LLM reply into a list of dicts, tolerating ```-fenced JSON."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return []
    if isinstance(data, dict):
        data = [data]
    return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []


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
        llm=None,
        promotion_access_count: int = 3,
        write_confidence_threshold: float = 0.5,
        trust_damping: float = 0.2,
        tracer: Optional[EzraTracer] = None,
    ) -> None:
        self._semantic = semantic_store
        self._llm = llm  # any object with async complete(messages) -> str; None disables extraction
        self._promotion_access_count = promotion_access_count
        self._write_threshold = write_confidence_threshold
        self._damping = trust_damping
        # Owns the `meta.learning` span for its pass (traced regardless of caller).
        self._tracer = tracer or EzraTracer.disabled()

    # -- 0. fact extraction (LLM) ---------------------------------------- #
    async def extract_facts(
        self,
        *,
        user_id: str,
        source_graph_id: str,
        agent_id: str,
        user_input: str,
        response: str,
        scope_topics: set[str] = frozenset(),
    ) -> list[SemanticFact]:
        """Extract durable semantic facts from a completed turn via the LLM.

        Returns ``[]`` when no LLM is configured or nothing parseable comes back —
        the safe path (write scoring drops anything low-confidence anyway).
        Extracted facts are tagged ``archival`` and attributed to this graph for
        cross-graph inheritance tracking.
        """
        if self._llm is None:
            return []
        prompt = (
            "Extract durable, reusable facts stated or decided in this exchange. "
            "A fact is a stable subject-predicate-object triple worth remembering "
            "across sessions (not small talk, not transient status). Respond ONLY "
            "with compact JSON: a list of objects "
            '{"subject": str, "predicate": str, "object": str, '
            '"topics": [str], "confidence": 0.0-1.0}. Empty list if none.\n\n'
            f"Agent: {agent_id}\nUser: {user_input}\nResponse: {response}"
        )
        try:
            raw = await self._llm.complete(
                [{"role": "user", "content": prompt}], temperature=0.0
            )
        except Exception:  # noqa: BLE001 — extraction is best-effort, never fatal
            return []

        now = _utcnow()
        facts: list[SemanticFact] = []
        for item in _parse_json_list(raw):
            try:
                subject = str(item["subject"]).strip()
                predicate = str(item["predicate"]).strip()
                obj = str(item["object"]).strip()
                confidence = float(item.get("confidence", 0.0))
            except (KeyError, TypeError, ValueError):
                continue
            if not (subject and predicate and obj):
                continue
            topics = [str(t) for t in item.get("topics", []) if str(t).strip()]
            if scope_topics:  # keep only in-scope topics, but never strip to empty
                topics = [t for t in topics if t in scope_topics] or topics
            facts.append(
                SemanticFact(
                    id=str(uuid4()),
                    user_id=user_id,
                    subject=subject,
                    predicate=predicate,
                    object=obj,
                    tier="archival",
                    topics=topics,
                    confidence=max(0.0, min(1.0, confidence)),
                    source_session_graph_ids=[source_graph_id],
                    created_at=now,
                    updated_at=now,
                )
            )
        return facts

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
        user_input: str = "",
        response: str = "",
        agent_id: str = "",
    ) -> LearningReport:
        with self._tracer.span(
            "meta.learning", agent_id=agent_id, user_id=user_id
        ) as span:
            report = LearningReport()
            candidates = list(fact_candidates)
            # When no explicit candidates are handed in, extract them from the turn
            # text via the LLM (no-op when no LLM is configured).
            if not candidates and self._llm is not None and response:
                candidates = await self.extract_facts(
                    user_id=user_id,
                    source_graph_id=source_graph_ids[0] if source_graph_ids else "",
                    agent_id=agent_id,
                    user_input=user_input,
                    response=response,
                    scope_topics=set(scope_topics),
                )
            report.persisted_fact_ids = await self.persist_writes(candidates)
            report.promoted_fact_ids = await self.promote_eligible(
                user_id=user_id,
                scope_topics=scope_topics,
                source_graph_ids=source_graph_ids,
            )
            for registration, topic, won in reconciliations:
                updated = self.record_reconciliation(registration, topic, won=won)
                report.trust_updates[f"{registration.agent_id}:{topic}"] = updated
            span.set_attributes(
                {
                    "meta.persisted_count": len(report.persisted_fact_ids),
                    "meta.promoted_count": len(report.promoted_fact_ids),
                    "meta.trust_update_count": len(report.trust_updates),
                }
            )
            return report
