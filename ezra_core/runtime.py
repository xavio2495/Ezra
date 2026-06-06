"""``Ezra`` — the composition root and public SDK entry point.

This is the wiring layer the rest of the platform was always missing: it
assembles the real backends (MongoDB Atlas cold tier, Redis hot tier, Qdrant
warm tier, the two-pass contradiction checker, the litellm adapter, the branch
manager, the two meta-agents, the OTel tracer) once, then hands out a scope-bound
``EzraService`` per agent via :meth:`Ezra.spawn_agent`. An ADK / LangGraph /
custom agent holds that service and talks to Ezra through it.

Two ways in:

* :meth:`Ezra.from_settings` / :meth:`Ezra.from_env` — production wiring against
  real Atlas/Redis/Qdrant + the local NLI checker (needs the ``ml`` deps; the
  heavy imports are lazy so importing this module stays cheap).
* the plain constructor — inject already-built components (in-memory stores, a
  fake LLM, an in-memory Qdrant) for unit tests.

The composition is deliberately thin — every component already exists and is
unit-tested; this module only connects them and owns their lifecycle
(:meth:`aclose`). Per-agent mesh connectors are passed to :meth:`spawn_agent`
(built by the caller, e.g. the demo orchestrator) so the runtime itself stays
source-agnostic.
"""

from __future__ import annotations

from typing import Optional

from ezra_core.adk_service.service import EzraService
from ezra_core.belief.branching import BranchManager
from ezra_core.belief.checker import ContradictionChecker
from ezra_core.belief.store import BeliefStore
from ezra_core.config import EzraSettings
from ezra_core.mesh.base import BaseConnector
from ezra_core.memory.semantic import SemanticStore
from ezra_core.meta_agent.learning import LearningMetaAgent
from ezra_core.meta_agent.lifecycle import LifecycleMetaAgent
from ezra_core.observability.tracer import EzraTracer
from ezra_core.policy.engine import PolicyEngine
from ezra_core.router import Router
from ezra_core.schemas.session_graph import MergeStrategy
from ezra_core.session_graph import SessionGraph, SessionGraphStore
from ezra_core.tiers.hot import HotTier
from ezra_core.tiers.warm import WarmTier


class Ezra:
    """Shared platform runtime. Build once; spawn one ``EzraService`` per agent."""

    def __init__(
        self,
        *,
        settings: EzraSettings,
        graph_store: SessionGraphStore,
        belief_store: BeliefStore,
        semantic_store: SemanticStore,
        hot: HotTier,
        llm,
        warm: Optional[WarmTier] = None,
        checker: Optional[ContradictionChecker] = None,
        policy: Optional[PolicyEngine] = None,
        branch_manager: Optional[BranchManager] = None,
        learning: Optional[LearningMetaAgent] = None,
        lifecycle: Optional[LifecycleMetaAgent] = None,
        tracer: Optional[EzraTracer] = None,
        parser=None,
        closers: tuple = (),
    ) -> None:
        self.settings = settings
        self.graph_store = graph_store
        self.belief_store = belief_store
        self.semantic_store = semantic_store
        self.hot = hot
        self.llm = llm
        self.warm = warm
        self.checker = checker
        self.policy = policy or PolicyEngine(enabled=settings.policy_engine_enabled)
        self.branch_manager = branch_manager
        self.learning = learning
        self.lifecycle = lifecycle
        self.tracer = tracer or EzraTracer.disabled()
        # Step-1 intent parser (drives intent-driven fetch); None disables it.
        self.parser = parser
        self._closers = closers

    # -- factories -------------------------------------------------------- #
    @classmethod
    def from_settings(cls, settings: EzraSettings, *, build_checker: bool = True) -> "Ezra":
        """Production wiring against real Atlas / Redis / Qdrant.

        Reuses the existing ``*_from_settings`` helpers. The cold-tier client is
        shared with the session-graph and branch stores so the whole runtime uses
        a single Atlas connection. ``build_checker`` is the only heavy step (it
        loads the local embedder + NLI model); turn it off where the two-pass
        checker isn't needed.
        """
        from pymongo import AsyncMongoClient
        from qdrant_client import AsyncQdrantClient

        from ezra_core.atlas_access import ensure_egress_allowed
        from ezra_core.belief.branching import MongoBranchStore
        from ezra_core.llm.adapter import GeminiEmbedder, llm_from_settings
        from ezra_core.observability.tracer import tracer_from_settings
        from ezra_core.session_graph import MongoSessionGraphStore
        from ezra_core.tiers.cold import cold_tier_from_settings
        from ezra_core.tiers.hot import hot_tier_from_settings

        # Allow this runtime's egress IP on Atlas before connecting (no-op locally).
        ensure_egress_allowed(settings)
        # One embedder shared by the warm tier and the archival-recall semantic store.
        embedder = GeminiEmbedder(
            settings.embedding_model, api_key=settings.llm_api_key or None
        )
        cold = cold_tier_from_settings(settings, embedder=embedder)
        client: AsyncMongoClient = cold.client
        graph_store = MongoSessionGraphStore(client, settings.mongodb_db)
        branch_store = MongoBranchStore(client, settings.mongodb_db)
        branch_manager = BranchManager(
            graph_store=graph_store,
            belief_store=cold.beliefs,
            branch_store=branch_store,
        )

        hot = hot_tier_from_settings(settings)

        qdrant = AsyncQdrantClient(url=settings.qdrant_url)
        warm = WarmTier(qdrant, embedder, ttl_hours=settings.warm_ttl_hours)

        checker = default_checker(settings) if build_checker else None

        llm = llm_from_settings(settings)
        tracer = tracer_from_settings(settings)
        learning = LearningMetaAgent(
            cold.semantic,
            llm=llm,
            promotion_access_count=settings.core_promotion_access_count,
            tracer=tracer,
        )
        lifecycle = LifecycleMetaAgent(
            graph_store, belief_store=cold.beliefs, warm=warm, tracer=tracer
        )

        from ezra_core.parse import parser_from_settings

        parser = parser_from_settings(settings)

        return cls(
            settings=settings,
            graph_store=graph_store,
            belief_store=cold.beliefs,
            semantic_store=cold.semantic,
            hot=hot,
            llm=llm,
            warm=warm,
            checker=checker,
            branch_manager=branch_manager,
            learning=learning,
            lifecycle=lifecycle,
            tracer=tracer,
            parser=parser,
            # Closed in order on aclose(); Redis/Qdrant clients expose aclose().
            closers=(cold, hot._r, qdrant),
        )

    @classmethod
    def from_env(cls, *, build_checker: bool = True) -> "Ezra":
        return cls.from_settings(EzraSettings(), build_checker=build_checker)

    # -- session graphs + agents ----------------------------------------- #
    async def create_session_graph(
        self,
        *,
        session_graph_id: str,
        description: str = "",
        merge_strategy: MergeStrategy = "last_write_wins",
        custom_resolver=None,
        inherits_from: Optional[list[str]] = None,
    ) -> SessionGraph:
        return await SessionGraph.create(
            store=self.graph_store,
            session_graph_id=session_graph_id,
            description=description,
            merge_strategy=merge_strategy,
            custom_resolver=custom_resolver,
            inherits_from=inherits_from,
            manual_resolution_timeout_seconds=self.settings.manual_resolution_timeout_seconds,
        )

    async def spawn_agent(
        self,
        graph: SessionGraph,
        *,
        agent_id: str,
        permission_scope: list[str],
        role: str = "",
        user_id: str = "",
        mesh: Optional[BaseConnector] = None,
    ) -> EzraService:
        """Register an agent on ``graph`` and return its scope-bound service.

        The per-agent ``Router`` and ``EzraService`` share the runtime's stores
        but carry this agent's identity + scope; ``mesh`` (optional) is the
        federated connector this agent is allowed to query. ``user_id`` attributes
        learning-extracted facts (the learning meta-agent runs after every turn).
        """
        await graph.spawn_agent(
            agent_id=agent_id, permission_scope=permission_scope, role=role
        )
        router = Router(
            hot=self.hot,
            belief_store=self.belief_store,
            llm=self.llm,
            warm=self.warm,
            semantic=self.semantic_store,
            policy=self.policy,
            mesh=mesh,
            context_limit=self.settings.context_limit,
            salience_decay_rate=self.settings.salience_decay_rate,
            archival_limit=self.settings.archival_recall_limit,
            tracer=self.tracer,
            learning=self.learning,
            parser=self.parser,
        )

        def trust_for(other_agent_id: str, topic: str) -> float:
            for reg in graph.active_agents:
                if reg.agent_id == other_agent_id:
                    return reg.trust_scores.get(topic, 1.0)
            return 1.0

        async def on_reconciled(contradiction, resolution) -> None:
            # Learning meta-agent: damp the winner's per-topic trust toward 1.0 and
            # the loser's toward 0.0 after a decisive reconciliation, then persist.
            if self.learning is None or resolution.decision not in ("accept_new", "keep_existing"):
                return
            new_won = resolution.decision == "accept_new"
            winner = agent_id if new_won else contradiction.existing_agent_id
            loser = contradiction.existing_agent_id if new_won else agent_id
            topic = contradiction.topic
            changed = False
            for reg in graph.active_agents:
                if reg.agent_id == winner:
                    self.learning.record_reconciliation(reg, topic, won=True)
                    changed = True
                elif reg.agent_id == loser:
                    self.learning.record_reconciliation(reg, topic, won=False)
                    changed = True
            if changed:
                await self.graph_store.save(graph.record)

        return EzraService(
            session_graph_id=graph.session_graph_id,
            agent_id=agent_id,
            permission_scope=permission_scope,
            user_id=user_id,
            belief_store=self.belief_store,
            router=router,
            warm=self.warm,
            checker=self.checker,
            mesh=mesh,
            branch_manager=self.branch_manager,
            policy=self.policy,
            merge_strategy=graph.record.merge_strategy,
            custom_resolver=graph.custom_resolver,
            manual_resolution_timeout_seconds=self.settings.manual_resolution_timeout_seconds,
            trust_for=trust_for,
            on_reconciled=on_reconciled,
        )

    # -- meta-agents ------------------------------------------------------ #
    async def run_lifecycle_tick(self, session_graph_id: str):
        """Run one scheduled lifecycle pass for a graph (state transitions, warm
        compaction, belief-retention TTL), traced as a ``meta.lifecycle`` span.

        This is the runtime hook a scheduler (or the demo loop) calls on the
        HANDOFF cadence (5 min / active graph, 1 hr / closed). Returns the
        ``LifecycleReport``; no-op (None) when no lifecycle agent is wired.
        """
        if self.lifecycle is None:
            return None
        # The lifecycle agent owns its own `meta.lifecycle` span.
        return await self.lifecycle.tick(session_graph_id)

    # -- lifecycle -------------------------------------------------------- #
    async def aclose(self) -> None:
        for closer in self._closers:
            close = getattr(closer, "aclose", None) or getattr(closer, "close", None)
            if close is None:
                continue
            result = close()
            if hasattr(result, "__await__"):
                await result


def default_checker(settings: EzraSettings) -> ContradictionChecker:
    """Build the local two-pass checker (MiniLM first pass + DeBERTa NLI second).

    Heavy: imports ``sentence_transformers`` (the optional ``ml`` group / torch).
    Kept out of module import and out of :meth:`Ezra.from_settings` unless asked.
    """
    from ezra_core.belief.checker import LocalNliClassifier, SentenceTransformerEmbedder

    return ContradictionChecker(
        SentenceTransformerEmbedder(device=settings.nli_device),
        LocalNliClassifier(model=settings.nli_model, device=settings.nli_device),
        similarity_threshold=settings.embedding_similarity_threshold,
        nli_confidence_threshold=settings.nli_confidence_threshold,
    )


def gemini_checker(settings: EzraSettings) -> ContradictionChecker:
    """Two-pass checker that uses Gemini for both passes — no torch.

    First pass = ``gemini-embedding-001`` cosine; second pass = a Gemini NLI call.
    Same non-negotiable two-pass architecture as :func:`default_checker`, but runs
    in the lean image (the local DeBERTa stays the GKE default). The embedding
    similarity threshold is lowered: Gemini embeddings cluster paraphrases lower
    than MiniLM, so 0.85 would miss same-topic candidate pairs.
    """
    from ezra_core.llm.adapter import GeminiEmbedder, GeminiNliClassifier, is_vertex_model

    # Vertex models authenticate via ADC (no key); AI Studio models use the key.
    embed_key = None if is_vertex_model(settings.embedding_model) else (settings.llm_api_key or None)
    nli_key = None if is_vertex_model(settings.meta_agent_model) else (settings.llm_api_key or None)
    return ContradictionChecker(
        GeminiEmbedder(settings.embedding_model, api_key=embed_key),
        GeminiNliClassifier(settings.meta_agent_model, api_key=nli_key),
        similarity_threshold=settings.gemini_checker_similarity_threshold,
        nli_confidence_threshold=settings.nli_confidence_threshold,
    )
