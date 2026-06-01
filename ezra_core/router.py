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
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from ezra_core.belief.store import BeliefStore
from ezra_core.memory.procedural import ProceduralStore
from ezra_core.memory.semantic import SemanticStore
from ezra_core.schemas.belief import Commitment
from ezra_core.schemas.memory import ProceduralRule, SemanticFact
from ezra_core.schemas.session_graph import AgentRegistration
from ezra_core.schemas.session_graph import SessionGraph as SessionGraphRecord


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
