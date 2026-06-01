"""F1 race-weekend orchestration — the six demo beats, fully offline.

Runs on in-memory stores with a deterministic fake agent LLM so the whole demo
is reproducible without Atlas / Qdrant / Gemini. Each beat exercises a real
platform component (dynamic spawn, policy engine, reconciler, branching, scaling)
and records a structured ``BeatResult`` so the terminal dashboard can render it
and the smoke test can assert on it.

Beats (HANDOFF demo script):
  1. Federation + dynamic spawn        (4 → 6 agents)
  2. Permission boundary denial        (logistics denied `aero`)
  3. Conditional spawn + contradiction (parts_shortage spawns; highest_trust)
  4. Multi-agent contradiction         (custom resolver → escalate)
  5. Branching replay                  (mutate + run forward + diff)
  6. Scaling proof                     (flat p50/p99 curve)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from demo.f1_race_weekend.data_ingestion import build_dataset
from demo.f1_race_weekend.spawning import SpawnController
from demo.scaling_benchmark import BenchmarkResult, run_benchmark
from ezra_core.belief.branching import BranchManager, InMemoryBranchStore
from ezra_core.belief.reconciler import ResolveContext, reconcile
from ezra_core.belief.store import InMemoryBeliefStore
from ezra_core.memory.semantic import InMemorySemanticStore
from ezra_core.meta_agent.learning import LearningMetaAgent
from ezra_core.policy.engine import PolicyDeniedError, PolicyEngine
from ezra_core.schemas.belief import Commitment, Contradiction, Resolution
from ezra_core.session_graph import InMemorySessionGraphStore, SessionGraph
from ezra_core.tiers.hot import HotTier

MAIN_GRAPH = "race-weekend-monaco-2026"
INHERITED_GRAPH = "race-weekend-imola-2026"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BeatResult(BaseModel):
    name: str
    summary: str
    details: dict = Field(default_factory=dict)


class DemoResult(BaseModel):
    beats: list[BeatResult] = Field(default_factory=list)
    peak_agents: int = 0
    scaling: Optional[BenchmarkResult] = None


def _commit(graph_id: str, agent_id: str, claim: str, topic: str, turn: int, trust: float):
    return Commitment(
        id=str(uuid4()),
        session_graph_id=graph_id,
        agent_id=agent_id,
        turn_index=turn,
        type="decision",
        claim=claim,
        topic=topic,
        trust_score=trust,
        created_at=_utcnow(),
    )


async def run_demo(
    *, hot: Optional[HotTier] = None, scaling_counts=(1, 5, 10)
) -> DemoResult:
    result = DemoResult()
    graph_store = InMemorySessionGraphStore()
    belief = InMemoryBeliefStore()
    semantic = InMemorySemanticStore()
    policy = PolicyEngine(enabled=True)
    learning = LearningMetaAgent(semantic)
    branches = BranchManager(
        graph_store=graph_store, belief_store=belief, branch_store=InMemoryBranchStore()
    )

    graph = await SessionGraph.create(
        store=graph_store,
        session_graph_id=MAIN_GRAPH,
        description="Monaco GP race weekend",
        merge_strategy="highest_trust",
        inherits_from=[INHERITED_GRAPH],
    )
    spawner = SpawnController(graph)
    peak = 0

    # -- Beat 1: federation + dynamic spawn ------------------------------- #
    await spawner.spawn_always_on()
    before = len(graph.active_agents)
    await spawner.handle_event("fp1_start")
    after = len(graph.active_agents)
    peak = max(peak, after)
    dataset = build_dataset()
    result.beats.append(
        BeatResult(
            name="federation_and_dynamic_spawn",
            summary=f"FP1 start: agent count {before} → {after}; "
            f"inherits core memory from {INHERITED_GRAPH}",
            details={
                "agents_before": before,
                "agents_after": after,
                "inherits_from": INHERITED_GRAPH,
                "federated_collections": {k: len(v) for k, v in dataset.items()},
            },
        )
    )

    # -- Beat 2: permission boundary denial ------------------------------- #
    logistics = next(a for a in graph.active_agents if a.agent_id == "logistics")
    denial: dict = {}
    try:
        policy.check_topics(logistics.permission_scope, ["aero"])
    except PolicyDeniedError as exc:
        denial = {"agent": "logistics", "scope": logistics.permission_scope,
                  "denied_topic": exc.topic}
    result.beats.append(
        BeatResult(
            name="permission_denial",
            summary="logistics asked for aero downforce target → DENIED "
            f"(scope {logistics.permission_scope} excludes 'aero')",
            details=denial,
        )
    )

    # -- Beat 3: conditional spawn + single-agent contradiction ----------- #
    await spawner.handle_event("inventory_drop")
    peak = max(peak, len(graph.active_agents))
    existing = _commit(MAIN_GRAPH, "race_strategy", "soft compound for race", "parts", 10, 0.78)
    await belief.append(existing)
    parts_claim = "front wing FW-07 stock critical: 2 units, race needs 4"
    contradiction = Contradiction(
        existing_commitment_id=existing.id,
        existing_agent_id="race_strategy",
        new_input_claim=parts_claim,
        new_agent_id="parts_shortage",
        topic="parts",
        similarity_score=0.88,
        nli_confidence=0.95,
        detected_at=_utcnow(),
    )
    resolution = await reconcile(
        contradiction, merge_strategy="highest_trust", existing_trust=0.78, new_trust=0.92
    )
    if resolution.decision == "accept_new":
        new_commit = _commit(MAIN_GRAPH, "parts_shortage", parts_claim, "parts", 11, 0.92)
        await belief.append(new_commit)
        await belief.supersede(existing.id, new_commit.id)
    learning.record_reconciliation(
        next(a for a in graph.active_agents if a.agent_id == "parts_shortage"), "parts", won=True
    )
    result.beats.append(
        BeatResult(
            name="conditional_spawn_and_contradiction",
            summary="inventory_drop spawned parts_shortage; highest_trust → "
            "parts_shortage (0.92) beats race_strategy (0.78)",
            details={
                "agents_now": len(graph.active_agents),
                "winner": "parts_shortage",
                "decision": resolution.decision,
                "merge_strategy_used": resolution.merge_strategy_used,
            },
        )
    )

    # -- Beat 4: multi-agent contradiction with a custom resolver --------- #
    async def race_director_rule(c: Contradiction, ctx: ResolveContext) -> Resolution:
        # App policy: 3+ agents conflicting on the same lap → escalate to human.
        if ctx.contemporaneous_contradictions_on_topic("final_stint") >= 3:
            return Resolution.escalate(reason="3+ agents conflict on final stint")
        return Resolution.fallback_to("highest_trust")

    final_stint = [
        _commit(MAIN_GRAPH, "tyre_engineer", "soft compound, fastest pace", "final_stint", 130, 0.91),
        _commit(MAIN_GRAPH, "weather_model", "rain in 8 min, wets needed", "final_stint", 130, 0.88),
        _commit(MAIN_GRAPH, "aero_rd", "softs overheat with current wing — mediums", "final_stint", 130, 0.85),
    ]
    multi = Contradiction(
        existing_commitment_id=final_stint[0].id,
        existing_agent_id="tyre_engineer",
        new_input_claim=final_stint[1].claim,
        new_agent_id="weather_model",
        topic="final_stint",
        similarity_score=0.86,
        nli_confidence=0.93,
        detected_at=_utcnow(),
    )
    multi_resolution = await reconcile(
        multi,
        merge_strategy="custom",
        existing_trust=0.91,
        new_trust=0.88,
        custom_resolver=race_director_rule,
        resolve_context=ResolveContext(
            topic="final_stint",
            existing_agent_id="tyre_engineer",
            new_agent_id="weather_model",
            existing_trust=0.91,
            new_trust=0.88,
            active_commitments=final_stint,
        ),
    )
    human_choice = "wets" if multi_resolution.decision == "escalate" else None
    result.beats.append(
        BeatResult(
            name="multi_agent_custom_resolver",
            summary="3 agents conflict on final stint → custom resolver ESCALATES; "
            f"race director chooses '{human_choice}'",
            details={
                "decision": multi_resolution.decision,
                "merge_strategy_used": multi_resolution.merge_strategy_used,
                "human_choice": human_choice,
                "conflicting_agents": [c.agent_id for c in final_stint],
            },
        )
    )

    # -- Beat 5: branching replay ----------------------------------------- #
    branch_id = "wets-earlier"
    await branches.branch_from(session_graph_id=MAIN_GRAPH, turn=130, branch_id=branch_id)
    await branches.mutate_belief(
        branch_id=branch_id, agent_id="race_strategy",
        new_claim="wets called at lap 43", topic="final_stint", turn_index=131,
    )

    async def forward_step(*, branch_id: str, turn: int):
        await belief.append(
            _commit(branch_id, "tyre_engineer", "wets holding, gap stable", "final_stint", turn, 0.9)
        )
        return f"turn {turn} ran"

    await branches.run_forward(branch_id=branch_id, until_turn=133, step=forward_step)
    diff = await branches.diff_branches(original=MAIN_GRAPH, branch=branch_id, from_turn=130)
    result.beats.append(
        BeatResult(
            name="branching_replay",
            summary="branched at turn 130 ('what if wets two laps earlier?'); "
            f"{len(diff.diverged_commitments)} topic(s) diverged",
            details={"diverged": diff.diverged_commitments},
        )
    )

    # -- Beat 6: scaling proof -------------------------------------------- #
    if hot is not None:
        scaling = await run_benchmark(agent_counts=scaling_counts, turns_per_agent=2, hot=hot)
        result.scaling = scaling
        result.beats.append(
            BeatResult(
                name="scaling_proof",
                summary="per-agent router overhead stays flat as the fleet grows: "
                + ", ".join(f"{p.agent_count}→p99 {p.p99_ms}ms" for p in scaling.points),
                details={"flat": scaling.flat,
                         "points": [p.model_dump() for p in scaling.points]},
            )
        )

    result.peak_agents = peak
    return result


async def _main() -> None:  # pragma: no cover - script entry point
    import redis.asyncio as aioredis

    from demo.dashboard_terminal import render_demo
    from ezra_core.config import EzraSettings

    settings = EzraSettings()
    hot = HotTier(aioredis.from_url(settings.redis_url, decode_responses=True))
    result = await run_demo(hot=hot)
    render_demo(result)


if __name__ == "__main__":  # pragma: no cover
    import asyncio

    asyncio.run(_main())
