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

from ezra_core.belief.branching import BranchManager
from ezra_core.belief.checker import ContradictionChecker
from ezra_core.belief.reconciler import CustomResolver, ResolveContext, reconcile
from ezra_core.belief.replay import reconstruct_state_at_turn, snapshot_now
from ezra_core.belief.store import BeliefStore
from ezra_core.mesh.base import BaseConnector
from ezra_core.policy.engine import PolicyEngine
from ezra_core.router import Router, TurnResult, write_back
from ezra_core.schemas.belief import BeliefSnapshot, Commitment, Contradiction, Resolution
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
        manual_resolution_timeout_seconds: int = 30,
        trust_for: Optional[Callable[[str, str], float]] = None,
        on_reconciled: Optional[
            Callable[[Contradiction, Resolution], Awaitable[None]]
        ] = None,
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
        self._manual_timeout = manual_resolution_timeout_seconds
        # (agent_id, topic) -> trust score; defaults to 1.0 when unknown.
        self._trust_for = trust_for or (lambda agent_id, topic: 1.0)
        # Post-reconciliation hook (learning meta-agent damps trust); no-op if None.
        self._on_reconciled = on_reconciled

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

        return CommitResult(
            commitment=commitment, contradiction=contradiction, resolution=resolution
        )

    async def query(
        self, query: str, *, topics: Sequence[str] = (), as_of=None
    ) -> MeshResult:
        # Policy gates first: an out-of-scope topic is denied regardless of whether
        # a connector exists (the agent must never even learn it could fetch it).
        self._policy.check_topics(self.permission_scope, topics)
        if self._mesh is None:
            raise RuntimeError("no mesh connector configured for this agent")
        return await self._mesh.fetch(query, self.agent_id, self.permission_scope, as_of)

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
