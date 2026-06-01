"""Router — the 8-step per-agent pipeline. This session wires two steps:

  - Step 4 (Hydrate): load scope-filtered core semantic memory from this graph
    AND every inherited graph at agent spawn; plus inherited procedural rules
    when the graph enables procedural inheritance.
  - Step 8 (Write-back): attribute a commitment to the agent and append it to
    the belief store; optionally persist extracted semantic facts.

Remaining steps (parse/policy/belief-check/fetch/assemble/LLM) arrive in later
sessions. LLM-based fact extraction belongs to the learning meta-agent
(Session 5); write-back here takes explicit, caller-provided facts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Literal, Optional, Sequence
from uuid import uuid4

from pydantic import BaseModel, Field

from ezra_core.belief.checker import ContradictionChecker
from ezra_core.belief.reconciler import (
    ContradictionCallback,
    CustomResolver,
    ResolveContext,
    reconcile,
)
from ezra_core.belief.replay import snapshot_now
from ezra_core.belief.store import BeliefStore
from ezra_core.mesh.base import BaseConnector
from ezra_core.memory.procedural import ProceduralStore
from ezra_core.memory.semantic import SemanticStore
from ezra_core.policy.engine import PolicyEngine
from ezra_core.schemas.belief import Commitment, Contradiction, Resolution
from ezra_core.schemas.context import AssembledContext, ContextSlot, ContextSlotType
from ezra_core.schemas.memory import ProceduralRule, SemanticFact
from ezra_core.schemas.mesh import MeshResult
from ezra_core.schemas.session_graph import AgentRegistration, MergeStrategy
from ezra_core.schemas.session_graph import SessionGraph as SessionGraphRecord
from ezra_core.tiers.hot import HotTier
from ezra_core.tiers.warm import WarmTier


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CombinedHydration(BaseModel):
    """Result of step-4 hydration: this graph's core facts, inherited core
    facts, and inherited procedural rules."""

    own_core: list[SemanticFact] = Field(default_factory=list)
    inherited_core: list[SemanticFact] = Field(default_factory=list)
    inherited_procedural: list[ProceduralRule] = Field(default_factory=list)

    @property
    def all_core(self) -> list[SemanticFact]:
        return [*self.own_core, *self.inherited_core]


async def hydrate_at_agent_spawn(
    *,
    graph: SessionGraphRecord,
    agent: AgentRegistration,
    user_id: str,
    semantic_store: SemanticStore,
    procedural_store: Optional[ProceduralStore] = None,
) -> CombinedHydration:
    scope = set(agent.permission_scope)

    own_core = await semantic_store.get_core(
        user_id=user_id,
        scope_topics=scope,
        source_graph_ids=[graph.session_graph_id],
    )

    inherited_core: list[SemanticFact] = []
    for inherited_graph_id in graph.inherits_from:
        inherited_core.extend(
            await semantic_store.get_core(
                user_id=user_id,
                scope_topics=scope,
                source_graph_ids=[inherited_graph_id],
            )
        )

    inherited_procedural: list[ProceduralRule] = []
    if graph.inherit_procedural and procedural_store is not None:
        for inherited_graph_id in graph.inherits_from:
            inherited_procedural.extend(
                await procedural_store.get_for_agent(
                    user_id=user_id,
                    scope_topics=scope,
                    source_graph_ids=[inherited_graph_id],
                )
            )

    return CombinedHydration(
        own_core=own_core,
        inherited_core=inherited_core,
        inherited_procedural=inherited_procedural,
    )


async def belief_check(
    *,
    checker: ContradictionChecker,
    commitments: Sequence[Commitment],
    new_claim: str,
    new_topic: str,
    new_agent_id: str,
    new_trust: float,
    merge_strategy: MergeStrategy,
    existing_trust_for: Optional[Callable[[str], float]] = None,
    custom_resolver: Optional[CustomResolver] = None,
    on_contradiction: Optional[ContradictionCallback] = None,
    manual_resolution_timeout_seconds: int = 30,
) -> tuple[Optional[Contradiction], Optional[Resolution]]:
    """Router step 3 (Belief): detect a contradiction (two-pass), and if found,
    reconcile it before the model is ever called. Returns (contradiction,
    resolution); both None when the new claim is consistent."""
    contradiction = checker.check(
        new_claim=new_claim,
        new_topic=new_topic,
        new_agent_id=new_agent_id,
        commitments=commitments,
    )
    if contradiction is None:
        return None, None

    existing_trust = (
        existing_trust_for(contradiction.existing_agent_id)
        if existing_trust_for is not None
        else 1.0
    )
    resolution = await reconcile(
        contradiction,
        merge_strategy=merge_strategy,
        existing_trust=existing_trust,
        new_trust=new_trust,
        manual_resolution_timeout_seconds=manual_resolution_timeout_seconds,
        custom_resolver=custom_resolver,
        on_contradiction=on_contradiction,
        resolve_context=ResolveContext(
            topic=contradiction.topic,
            existing_agent_id=contradiction.existing_agent_id,
            new_agent_id=contradiction.new_agent_id,
            existing_trust=existing_trust,
            new_trust=new_trust,
            active_commitments=commitments,
        ),
    )
    return contradiction, resolution


async def fetch(
    *,
    connector: BaseConnector,
    policy: PolicyEngine,
    query: str,
    agent_id: str,
    permission_scope: list[str],
    topics: Sequence[str],
    as_of: Optional[datetime] = None,
) -> MeshResult:
    """Router step 5 (Fetch): policy-gate the federated query by topic, then
    push down to the connector. Raises PolicyDeniedError if a topic is out of
    scope — the model never sees data the agent isn't allowed to fetch."""
    policy.check_topics(permission_scope, topics)
    return await connector.fetch(query, agent_id, permission_scope, as_of)


async def write_back(
    *,
    belief_store: BeliefStore,
    session_graph_id: str,
    agent_id: str,
    turn_index: int,
    claim: str,
    topic: str,
    type: Literal["fact", "decision", "calculation", "constraint"] = "fact",
    value: Optional[Any] = None,
    trust_score: float = 1.0,
    semantic_store: Optional[SemanticStore] = None,
    semantic_facts: Optional[list[SemanticFact]] = None,
) -> Commitment:
    commitment = Commitment(
        id=str(uuid4()),
        session_graph_id=session_graph_id,
        agent_id=agent_id,
        turn_index=turn_index,
        type=type,
        claim=claim,
        value=value,
        topic=topic,
        trust_score=trust_score,
        created_at=_utcnow(),
    )
    await belief_store.append(commitment)

    if semantic_store is not None and semantic_facts:
        for fact in semantic_facts:
            await semantic_store.add(fact)

    return commitment


# --------------------------------------------------------------------------- #
# Full 8-step router (per-agent turn assembly)
# --------------------------------------------------------------------------- #
def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def compute_salience(
    slot_type: ContextSlotType,
    age_turns: int,
    base_salience: float,
    *,
    decay_rate: float = 0.1,
) -> float:
    if slot_type in (ContextSlotType.PINNED_BELIEF, ContextSlotType.CURRENT_INPUT):
        return 1.0
    return max(base_salience * ((1 - decay_rate) ** age_turns), 0.0)


class TurnResult(BaseModel):
    agent_id: str
    response: str
    context: AssembledContext
    pinned_beliefs: list[Commitment] = Field(default_factory=list)
    mesh_result: Optional[MeshResult] = None


class Router:
    """Assembles the smallest high-signal context for one agent turn and calls
    the model. Steps: 2 policy-gate the optional mesh fetch · 3 load scope-
    filtered pinned beliefs · 4 hydrate warm summaries + hot turns · 5 fetch ·
    6 assemble (salience-ranked, budget-capped) · 7 LLM · 8 write-back to hot."""

    def __init__(
        self,
        *,
        hot: HotTier,
        belief_store: BeliefStore,
        llm,
        warm: Optional[WarmTier] = None,
        policy: Optional[PolicyEngine] = None,
        mesh: Optional[BaseConnector] = None,
        context_limit: int = 128000,
        salience_decay_rate: float = 0.1,
        warm_limit: int = 5,
    ) -> None:
        self._hot = hot
        self._belief = belief_store
        self._llm = llm
        self._warm = warm
        self._policy = policy or PolicyEngine(enabled=False)
        self._mesh = mesh
        self._context_limit = context_limit
        self._decay = salience_decay_rate
        self._warm_limit = warm_limit

    async def run_turn(
        self,
        *,
        agent: AgentRegistration,
        user_input: str,
        system_prompt: str = "",
        mesh_query: Optional[str] = None,
        mesh_topics: Sequence[str] = (),
        as_of: Optional[datetime] = None,
    ) -> TurnResult:
        scope = set(agent.permission_scope)
        graph_id = agent.session_graph_id

        # Step 5 (Fetch) — policy-gated; only if a mesh query was requested.
        mesh_result: Optional[MeshResult] = None
        if mesh_query and self._mesh is not None:
            mesh_result = await fetch(
                connector=self._mesh,
                policy=self._policy,
                query=mesh_query,
                agent_id=agent.agent_id,
                permission_scope=list(agent.permission_scope),
                topics=mesh_topics,
                as_of=as_of,
            )

        # Step 3 (Belief) — scope-filtered active commitments become pinned context.
        belief_snap = await snapshot_now(self._belief, graph_id, scope_topics=scope)

        # Step 4 (Hydrate) — warm recall + recent hot turns.
        warm_summaries = []
        if self._warm is not None:
            warm_summaries = await self._warm.recall(
                session_graph_id=graph_id,
                query=user_input,
                scope_topics=scope,
                limit=self._warm_limit,
            )
        hot_turns = await self._hot.get_turns(graph_id, agent.agent_id)

        # Step 6 (Assemble) — salience-ranked, budget-capped.
        context = self._assemble(
            agent=agent,
            system_prompt=system_prompt,
            beliefs=belief_snap.commitments,
            warm_summaries=warm_summaries,
            hot_turns=hot_turns,
            mesh_result=mesh_result,
            user_input=user_input,
        )

        # Step 7 (LLM).
        response = await self._llm.complete(self._to_messages(context, user_input))

        # Step 8 (Write-back) — record the turn in the hot tier.
        await self._hot.append_turn(
            graph_id, agent.agent_id, {"input": user_input, "response": response}
        )

        return TurnResult(
            agent_id=agent.agent_id,
            response=response,
            context=context,
            pinned_beliefs=belief_snap.commitments,
            mesh_result=mesh_result,
        )

    def _assemble(
        self,
        *,
        agent: AgentRegistration,
        system_prompt: str,
        beliefs: list[Commitment],
        warm_summaries: list,
        hot_turns: list[dict[str, Any]],
        mesh_result: Optional[MeshResult],
        user_input: str,
    ) -> AssembledContext:
        candidates: list[ContextSlot] = []

        if system_prompt:
            candidates.append(
                ContextSlot(
                    slot_type=ContextSlotType.SYSTEM, content=system_prompt, salience=1.0,
                    token_cost=_estimate_tokens(system_prompt),
                )
            )
        for c in beliefs:
            candidates.append(
                ContextSlot(
                    slot_type=ContextSlotType.PINNED_BELIEF,
                    content=f"[{c.agent_id}] {c.claim}",
                    salience=1.0,
                    token_cost=_estimate_tokens(c.claim),
                    topics=[c.topic],
                )
            )
        for s in warm_summaries:
            candidates.append(
                ContextSlot(
                    slot_type=ContextSlotType.WARM_SUMMARY,
                    content=s.summary,
                    salience=compute_salience(
                        ContextSlotType.WARM_SUMMARY, 0, s.salience, decay_rate=self._decay
                    ),
                    token_cost=_estimate_tokens(s.summary),
                    topics=s.topics,
                )
            )
        # Oldest hot turn = highest age; newest = age 0.
        for age, turn in enumerate(reversed(hot_turns)):
            text = f"{turn.get('input', '')} -> {turn.get('response', '')}"
            candidates.append(
                ContextSlot(
                    slot_type=ContextSlotType.HOT_TURN,
                    content=text,
                    salience=compute_salience(
                        ContextSlotType.HOT_TURN, age, 1.0, decay_rate=self._decay
                    ),
                    token_cost=_estimate_tokens(text),
                )
            )
        if mesh_result is not None:
            content = f"{mesh_result.provenance.source}: {mesh_result.data}"
            candidates.append(
                ContextSlot(
                    slot_type=ContextSlotType.MESH_RESULT,
                    content=content,
                    salience=0.9,
                    token_cost=_estimate_tokens(content),
                    topics=mesh_result.topics,
                )
            )
        candidates.append(
            ContextSlot(
                slot_type=ContextSlotType.CURRENT_INPUT, content=user_input, salience=1.0,
                token_cost=_estimate_tokens(user_input),
            )
        )

        # Fill the budget from highest salience down.
        chosen: list[ContextSlot] = []
        total = 0
        for slot in sorted(candidates, key=lambda s: s.salience, reverse=True):
            if total + slot.token_cost > self._context_limit:
                continue
            chosen.append(slot)
            total += slot.token_cost

        return AssembledContext(
            session_graph_id=agent.session_graph_id,
            agent_id=agent.agent_id,
            slots=chosen,
            total_tokens=total,
        )

    @staticmethod
    def _to_messages(context: AssembledContext, user_input: str) -> list[dict[str, str]]:
        system_parts = [
            slot.content
            for slot in context.slots
            if slot.slot_type != ContextSlotType.CURRENT_INPUT
        ]
        return [
            {"role": "system", "content": "\n".join(system_parts)},
            {"role": "user", "content": user_input},
        ]
