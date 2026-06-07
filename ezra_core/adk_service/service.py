"""EzraService — a scope-bound façade over the platform for a single agent.

An agent (ADK, LangGraph, custom — framework-agnostic) holds one of these,
constructed with its identity + permission scope and the shared platform
components. Every method is automatically scope-filtered for this agent.

This is deliberately thin: it wires already-built components (belief store,
warm tier, router, checker, mesh connector, branch manager) to the documented
``recall / query / belief_check / belief_snapshot / write_back / commit /
complete / replay / branch_from`` surface. The composition root (``Ezra`` in
``runtime.py``) builds these and hands one out per agent via ``spawn_agent``.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional, Sequence

from pydantic import BaseModel

from ezra_core.audit.store import AuditLog
from ezra_core.belief.branching import BranchManager
from ezra_core.belief.checker import ContradictionChecker
from ezra_core.belief.history import revert_commitment, rewind_to_turn
from ezra_core.belief.reconciler import (
    ContradictionCallback,
    CustomResolver,
    ResolveContext,
    reconcile,
)
from ezra_core.belief.replay import reconstruct_state_at_turn, snapshot_now
from ezra_core.belief.store import BeliefStore
from ezra_core.mesh.base import BaseConnector
from ezra_core.policy.engine import PolicyDeniedError, PolicyEngine
from ezra_core.router import Router, TurnResult, write_back
from ezra_core.schemas.belief import (
    BeliefSnapshot,
    Commitment,
    Contradiction,
    Resolution,
    RewindResult,
)
from ezra_core.schemas.branch import Branch
from ezra_core.schemas.mesh import MeshResult
from ezra_core.schemas.memory import WarmSummary
from ezra_core.schemas.session_graph import AgentRegistration, MergeStrategy
from ezra_core.tiers.warm import WarmTier


class CommitResult(BaseModel):
    """Outcome of :meth:`EzraService.commit` — the new commitment plus, when a
    contradiction was detected, the contradiction and how it was resolved."""

    commitment: Commitment
    contradiction: Optional[Contradiction] = None
    resolution: Optional[Resolution] = None


class EzraService:
    def __init__(
        self,
        *,
        session_graph_id: str,
        agent_id: str,
        permission_scope: list[str],
        belief_store: BeliefStore,
        user_id: str = "",
        router: Optional[Router] = None,
        warm: Optional[WarmTier] = None,
        checker: Optional[ContradictionChecker] = None,
        mesh: Optional[BaseConnector] = None,
        branch_manager: Optional[BranchManager] = None,
        policy: Optional[PolicyEngine] = None,
        merge_strategy: MergeStrategy = "last_write_wins",
        custom_resolver: Optional[CustomResolver] = None,
        on_contradiction: Optional[ContradictionCallback] = None,
        manual_resolution_timeout_seconds: int = 30,
        trust_for: Optional[Callable[[str, str], float]] = None,
        on_reconciled: Optional[
            Callable[[Contradiction, Resolution], Awaitable[None]]
        ] = None,
        audit_log: Optional[AuditLog] = None,
    ) -> None:
        self.session_graph_id = session_graph_id
        self.agent_id = agent_id
        self.permission_scope = list(permission_scope)
        self.user_id = user_id
        self._belief = belief_store
        self._router = router
        self._warm = warm
        self._checker = checker
        self._mesh = mesh
        self._branches = branch_manager
        self._policy = policy or PolicyEngine(enabled=False)
        self._merge_strategy = merge_strategy
        self._custom_resolver = custom_resolver
        # Manual-mode callback (registered via @ezra.on_contradiction); the
        # reconciler blocks on it up to manual_resolution_timeout_seconds.
        self._on_contradiction = on_contradiction
        self._manual_timeout = manual_resolution_timeout_seconds
        # (agent_id, topic) -> trust score; defaults to 1.0 when unknown.
        self._trust_for = trust_for or (lambda agent_id, topic: 1.0)
        # Post-reconciliation hook (learning meta-agent damps trust); no-op if None.
        self._on_reconciled = on_reconciled
        # Activity-feed sink; events are written best-effort, never blocking.
        self._audit = audit_log

    @property
    def _scope(self) -> set[str]:
        return set(self.permission_scope)

    def _registration(self) -> AgentRegistration:
        from datetime import datetime, timezone

        return AgentRegistration(
            agent_id=self.agent_id,
            session_graph_id=self.session_graph_id,
            permission_scope=self.permission_scope,
            spawned_at=datetime.now(timezone.utc),
        )

    async def _record(self, event_type: str, *, topic: str = "", **detail: Any) -> None:
        """Append one activity-feed event. Best-effort: a logging failure must
        never break the operation that produced it."""
        if self._audit is None:
            return
        from datetime import datetime, timezone
        from uuid import uuid4

        from ezra_core.schemas.audit import AuditEvent

        try:
            await self._audit.append(
                AuditEvent(
                    id=uuid4().hex,
                    session_graph_id=self.session_graph_id,
                    agent_id=self.agent_id,
                    event_type=event_type,  # type: ignore[arg-type]
                    topic=topic,
                    detail=detail,
                    created_at=datetime.now(timezone.utc),
                )
            )
        except Exception:
            pass

    async def recall(self, query: str, *, limit: int = 5) -> list[WarmSummary]:
        if self._warm is None:
            return []
        return await self._warm.recall(
            session_graph_id=self.session_graph_id,
            query=query,
            scope_topics=self._scope,
            limit=limit,
        )

    async def belief_snapshot(self, *, as_of_turn: Optional[int] = None) -> BeliefSnapshot:
        if as_of_turn is not None:
            return await reconstruct_state_at_turn(
                self._belief, self.session_graph_id, as_of_turn, scope_topics=self._scope
            )
        return await snapshot_now(self._belief, self.session_graph_id, scope_topics=self._scope)

    async def belief_check(self, claim: str, topic: str) -> Optional[Contradiction]:
        if self._checker is None:
            return None
        self._policy.check_topic(self.permission_scope, topic)
        active = await self._belief.get_active(self.session_graph_id, topic=topic)
        return self._checker.check(
            new_claim=claim, new_topic=topic, new_agent_id=self.agent_id, commitments=active
        )

    async def write_back(
        self,
        claim: str,
        topic: str,
        *,
        turn_index: int,
        type: str = "fact",
        value: Any = None,
        trust_score: float = 1.0,
    ) -> Commitment:
        self._policy.check_topic(self.permission_scope, topic)
        return await write_back(
            belief_store=self._belief,
            session_graph_id=self.session_graph_id,
            agent_id=self.agent_id,
            turn_index=turn_index,
            claim=claim,
            topic=topic,
            type=type,  # type: ignore[arg-type]
            value=value,
            trust_score=trust_score,
        )

    async def commit(
        self,
        claim: str,
        topic: str,
        *,
        turn_index: int,
        type: str = "decision",
        value: Any = None,
        trust_score: Optional[float] = None,
    ) -> "CommitResult":
        """Commit a belief WITH contradiction handling — the full step-3+8 flow.

        Detects a contradiction against active commitments on ``topic`` (two-pass
        checker), reconciles it with the graph's merge strategy, writes the new
        commitment, and supersedes the loser when the new claim wins. This is the
        surface an agent uses to "say something" through Ezra; the ADK
        ``commit_belief`` tool is a thin wrapper over it.

        ``trust_score`` defaults to THIS agent's per-topic trust (so highest_trust
        reconciliation reflects the agents' standing, not commit order).
        """
        self._policy.check_topic(self.permission_scope, topic)
        if trust_score is None:
            trust_score = self._trust_for(self.agent_id, topic)

        contradiction: Optional[Contradiction] = None
        resolution: Optional[Resolution] = None
        if self._checker is not None:
            active = await self._belief.get_active(self.session_graph_id, topic=topic)
            contradiction = self._checker.check(
                new_claim=claim,
                new_topic=topic,
                new_agent_id=self.agent_id,
                commitments=active,
            )
            if contradiction is not None:
                existing_trust = self._trust_for(contradiction.existing_agent_id, topic)
                resolution = await reconcile(
                    contradiction,
                    merge_strategy=self._merge_strategy,
                    existing_trust=existing_trust,
                    new_trust=trust_score,
                    manual_resolution_timeout_seconds=self._manual_timeout,
                    custom_resolver=self._custom_resolver,
                    on_contradiction=self._on_contradiction,
                    resolve_context=ResolveContext(
                        topic=topic,
                        existing_agent_id=contradiction.existing_agent_id,
                        new_agent_id=self.agent_id,
                        existing_trust=existing_trust,
                        new_trust=trust_score,
                        active_commitments=active,
                    ),
                )

        commitment = await write_back(
            belief_store=self._belief,
            session_graph_id=self.session_graph_id,
            agent_id=self.agent_id,
            turn_index=turn_index,
            claim=claim,
            topic=topic,
            type=type,  # type: ignore[arg-type]
            value=value,
            trust_score=trust_score,
        )
        if (
            contradiction is not None
            and resolution is not None
            and resolution.decision == "accept_new"
        ):
            await self._belief.supersede(contradiction.existing_commitment_id, commitment.id)

        # Hand the resolved contradiction to the learning meta-agent (damped trust
        # updates for winner/loser). Best-effort: never block the commit on it.
        if contradiction is not None and resolution is not None and self._on_reconciled:
            await self._on_reconciled(contradiction, resolution)

        # Activity feed: the commit, and (if one fired) the detected contradiction
        # + how it reconciled.
        await self._record(
            "belief_committed", topic=topic, claim=claim, commitment_id=commitment.id,
            turn_index=turn_index, trust_score=trust_score,
        )
        if contradiction is not None:
            await self._record(
                "contradiction_detected", topic=topic, new_claim=claim,
                with_agent=contradiction.existing_agent_id,
                similarity=contradiction.similarity_score,
                nli_confidence=contradiction.nli_confidence,
            )
            if resolution is not None:
                await self._record(
                    "contradiction_reconciled", topic=topic,
                    decision=resolution.decision,
                    strategy=resolution.merge_strategy_used,
                    with_agent=contradiction.existing_agent_id,
                )

        return CommitResult(
            commitment=commitment, contradiction=contradiction, resolution=resolution
        )

    async def revert(
        self, commitment_id: str, *, reason: str, turn_index: int
    ) -> Commitment:
        """Git-revert a single commitment: drop it from the active belief state by
        appending an append-only ``revert`` marker (history is preserved). Returns
        the marker commitment."""
        marker = await revert_commitment(
            self._belief,
            session_graph_id=self.session_graph_id,
            commitment_id=commitment_id,
            by_agent=self.agent_id,
            reason=reason,
            turn_index=turn_index,
        )
        await self._record(
            "belief_reverted", commitment_id=commitment_id, reason=reason,
            marker_id=marker.id,
        )
        return marker

    async def rewind(self, turn: int, *, reason: str) -> RewindResult:
        """Rewind the live graph to its as-of-``turn`` belief state (append-only):
        undo every commitment made after ``turn`` and restore the ones a now-undone
        commitment had superseded. History stays intact and replayable."""
        result = await rewind_to_turn(
            self._belief,
            session_graph_id=self.session_graph_id,
            turn=turn,
            by_agent=self.agent_id,
            reason=reason,
        )
        await self._record(
            "belief_rewound", reason=reason, rewound_to_turn=result.rewound_to_turn,
            undone=len(result.superseded_ids), restored=len(result.reactivated_ids),
        )
        return result

    async def query(
        self, query: str, *, topics: Sequence[str] = (), as_of=None
    ) -> MeshResult:
        # Policy gates first: an out-of-scope topic is denied regardless of whether
        # a connector exists (the agent must never even learn it could fetch it).
        try:
            self._policy.check_topics(self.permission_scope, topics)
        except PolicyDeniedError as exc:
            await self._record(
                "fetch_denied", topic=exc.topic, query=query, scope=self.permission_scope
            )
            raise
        if self._mesh is None:
            raise RuntimeError("no mesh connector configured for this agent")
        result = await self._mesh.fetch(query, self.agent_id, self.permission_scope, as_of)
        rows = (
            len(result.data)
            if isinstance(result.data, list)
            else (0 if result.data is None else 1)
        )
        await self._record(
            "federated_fetch", topic=(topics[0] if topics else ""),
            source=result.provenance.source,
            time_travel_available=result.provenance.time_travel_available, rows=rows,
        )
        return result

    async def complete(self, user_input: str, *, system_prompt: str = "", **kwargs) -> TurnResult:
        if self._router is None:
            raise RuntimeError("no router configured for this agent")
        kwargs.setdefault("user_id", self.user_id)
        return await self._router.run_turn(
            agent=self._registration(),
            user_input=user_input,
            system_prompt=system_prompt,
            **kwargs,
        )

    async def replay(self, turn: int) -> BeliefSnapshot:
        return await reconstruct_state_at_turn(
            self._belief, self.session_graph_id, turn, scope_topics=self._scope
        )

    async def branch_from(self, turn: int, branch_id: str, *, description: str = "") -> Branch:
        if self._branches is None:
            raise RuntimeError("no branch manager configured")
        return await self._branches.branch_from(
            session_graph_id=self.session_graph_id,
            turn=turn,
            branch_id=branch_id,
            description=description or None,
        )
