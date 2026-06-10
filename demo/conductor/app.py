"""FastAPI Demo Conductor (claude-docs/demo-dashboard-plan.md §4/§6).

One process: spawns the F1 fleet into a session graph over a real ``Ezra``, runs a
real Ezra turn per presenter prompt, performs the presenter ops (rewind / revert /
branch), and streams ``message_event`` + ``audit`` SSE to the dashboard.

Two turn modes:

- **live** (GKE): the prompt drives a real ADK agent over Vertex Gemini
  (``orchestrator._run_agent``) — the agent's LLM decides what to commit.
- **offline** (dev, this machine has no GCP creds): ``service.complete`` runs the
  full 8-step router turn against the in-memory runtime, and the commit the tuned
  briefing *instructs* the agent to make is applied deterministically through the
  same ``service.commit`` path — so detection, reconciliation, supersession, and
  the audit feed are all the real platform, only the LLM is a stand-in.

Honesty rule: every state change the UI shows flows from the persisted
``AuditEvent`` feed; the conductor never invents events.
"""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from demo.f1_race_weekend.adk_runtime.fleet import FLEET_ROLES, INHERITED_GRAPH, _mesh_for
from demo.f1_race_weekend.agents.roles import role_by_id
from ezra_core.audit.store import InMemoryAuditLog
from ezra_core.policy.engine import PolicyDeniedError
from ezra_core.runtime import Ezra
from ezra_core.schemas.belief import MARKER_TYPES

CONDUCTOR_GRAPH = "race-weekend-monaco-2026-demo"
DEFAULT_TRUST = {"tyre_engineer": 0.95, "race_strategy": 0.80}

# The tuned briefings (fleet.FLEET_PROMPTS / the chat pre-fills) spell out the
# exact claim + topic the agent must commit. Offline mode parses that instruction
# instead of asking an LLM to follow it.
_EXACT_CLAIM = re.compile(r"EXACTLY this claim[^:]*:\s*'([^']+)'")
_TOPIC = re.compile(r"topic\s+'([^']+)'")
_WANTS_COMMIT = re.compile(r"\bcommit\b", re.IGNORECASE)


class PromptBody(BaseModel):
    text: str


class RewindBody(BaseModel):
    turn: int = 1
    reason: str = "presenter rewind"


class RevertBody(BaseModel):
    commitment_id: Optional[str] = None
    reason: str = "presenter revert"


class Conductor:
    def __init__(self, ezra: Ezra, *, offline: bool) -> None:
        self.ezra = ezra
        self.offline = offline
        self.graph = None
        self.services: dict[str, Any] = {}
        self.turn_index = 0
        self.branch_count = 0
        self._subscribers: set[asyncio.Queue] = set()
        # The audit feed is the contract with the UI — make sure one exists even
        # on a bare offline runtime (from_settings wires Mongo-backed one).
        if self.ezra.audit_log is None:
            self.ezra.audit_log = InMemoryAuditLog()

    # -- SSE hub -------------------------------------------------------------- #
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def publish_message(self, payload: dict) -> None:
        for q in self._subscribers:
            q.put_nowait(payload)

    async def audit_snapshot(self) -> list[dict]:
        if self.graph is None:
            return []
        events = await self.ezra.audit_log.get_for_graph(CONDUCTOR_GRAPH, limit=1000)
        return [e.model_dump(mode="json") for e in events]

    # -- presenter ops -------------------------------------------------------- #
    async def start(self) -> dict:
        if self.graph is None:
            self.graph = await self.ezra.create_session_graph(
                session_graph_id=CONDUCTOR_GRAPH,
                description="Monaco GP live demo fleet (conductor)",
                merge_strategy="highest_trust",
                inherits_from=[INHERITED_GRAPH],
            )
            for role_id in FLEET_ROLES:
                role = role_by_id(role_id)
                self.services[role_id] = await self.ezra.spawn_agent(
                    self.graph,
                    agent_id=role.agent_id,
                    permission_scope=role.permission_scope,
                    role=role.role,
                    mesh=_mesh_for(self.ezra, role_id),
                )
            # Seed per-topic trust BEFORE any turn so highest_trust has a defined
            # winner on 'tyres' (same as fleet.run_fleet).
            for reg in self.graph.active_agents:
                if reg.agent_id in DEFAULT_TRUST:
                    reg.trust_scores["tyres"] = DEFAULT_TRUST[reg.agent_id]
            await self.ezra.graph_store.save(self.graph.record)
        return {
            "graph_id": CONDUCTOR_GRAPH,
            "mode": "offline" if self.offline else "live",
            "agents": [
                {"id": r, "role": role_by_id(r).role, "scope": role_by_id(r).permission_scope}
                for r in self.services
            ],
        }

    async def prompt(self, agent_id: str, text: str) -> dict:
        if agent_id not in self.services:
            raise HTTPException(status_code=404, detail=f"unknown agent {agent_id!r}")
        self.turn_index += 1
        if self.offline:
            payload = await self._offline_turn(agent_id, text, self.turn_index)
        else:
            payload = await self._live_turn(agent_id, text)
        self.publish_message(payload)
        return payload

    async def _offline_turn(self, agent_id: str, text: str, turn_index: int) -> dict:
        service = self.services[agent_id]
        result = await service.complete(text)  # real 8-step router turn (stand-in LLM)
        response = result.response
        committed = None
        topic_match = _TOPIC.search(text)
        if topic_match and _WANTS_COMMIT.search(text):
            topic = topic_match.group(1)
            claim_match = _EXACT_CLAIM.search(text)
            claim = (
                claim_match.group(1)
                if claim_match
                else f"{role_by_id(agent_id).role}: {topic} posture nominal."
            )
            try:
                commit = await service.commit(claim, topic, turn_index=turn_index)
                committed = {"topic": topic, "claim": commit.commitment.claim}
                response = f"{response}\n[offline] committed on '{topic}': {claim}"
            except PolicyDeniedError as exc:
                response = f"{response}\n[offline] commit DENIED: {exc}"
        return self._message(agent_id, response, committed)

    async def _live_turn(self, agent_id: str, text: str) -> dict:
        from demo.f1_race_weekend.adk_runtime.orchestrator import _run_agent

        turn = await _run_agent(
            self.services[agent_id],
            role_by_id(agent_id),
            text,
            self.ezra.settings.llm_model,
            self.ezra.settings.llm_api_key,
        )
        committed = (
            {"topic": turn.committed[-1]["topic"], "claim": turn.committed[-1]["claim"]}
            if turn.committed
            else None
        )
        return self._message(agent_id, turn.response, committed)

    def _message(self, agent_id: str, text: str, committed: Optional[dict]) -> dict:
        return {
            "agent_id": agent_id,
            "role": "agent",
            "text": text,
            "committed": committed,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def rewind(self, turn: int, reason: str) -> dict:
        service = self._any_service()
        result = await service.rewind(turn, reason=reason)
        return result.model_dump(mode="json")

    async def revert(self, commitment_id: Optional[str], reason: str) -> dict:
        target_id = commitment_id
        owner = None
        commitments = [
            c
            for c in await self.ezra.belief_store.get_active(CONDUCTOR_GRAPH)
            if c.type not in MARKER_TYPES
        ]
        if target_id is None:
            if not commitments:
                raise HTTPException(status_code=409, detail="no active commitments to revert")
            latest = max(commitments, key=lambda c: c.turn_index)
            target_id, owner = latest.id, latest.agent_id
        else:
            owner = next((c.agent_id for c in commitments if c.id == target_id), None)
        # Revert through the owning agent's service so the marker is honestly
        # attributed; fall back to any service for an unknown owner.
        service = self.services.get(owner) or self._any_service()
        self.turn_index += 1
        marker = await service.revert(target_id, reason=reason, turn_index=self.turn_index)
        return {"reverted": target_id, "marker_id": marker.id}

    async def branch(self) -> dict:
        if self.ezra.branch_manager is None:
            raise HTTPException(status_code=409, detail="branching not wired")
        self.branch_count += 1
        branch_id = f"{CONDUCTOR_GRAPH}-whatif-{self.branch_count}"
        await self.ezra.branch_manager.branch_from(
            session_graph_id=CONDUCTOR_GRAPH, turn=1, branch_id=branch_id
        )
        await self.ezra.branch_manager.mutate_belief(
            branch_id=branch_id,
            agent_id="race_strategy",
            new_claim="wets called at lap 43",
            topic="tyres",
            turn_index=2,
        )
        diff = await self.ezra.branch_manager.diff_branches(
            original=CONDUCTOR_GRAPH, branch=branch_id, from_turn=1
        )
        return {"branch_id": branch_id, "diverged": diff.diverged_commitments}

    def _any_service(self):
        if not self.services:
            raise HTTPException(status_code=409, detail="fleet not started")
        return next(iter(self.services.values()))


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def create_app(ezra: Optional[Ezra] = None, *, offline: Optional[bool] = None) -> FastAPI:
    """Build the conductor app. With no ``ezra``, wires the in-memory offline
    runtime (no Atlas/Redis/Qdrant/Gemini) — pass ``Ezra.from_env()`` for live."""
    owns_ezra = ezra is None
    if ezra is None:
        from examples._harness import build_offline_ezra

        ezra = build_offline_ezra()
        if offline is None:
            offline = True
    conductor = Conductor(ezra, offline=bool(offline))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        if owns_ezra:
            await ezra.aclose()

    app = FastAPI(title="Ezra Demo Conductor", lifespan=lifespan)
    # Dev convenience: the Vite dev server runs on its own origin. In production
    # the conductor serves the built UI itself (single origin on GKE).
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )
    app.state.conductor = conductor

    @app.post("/demo/start")
    async def start() -> dict:
        return await conductor.start()

    @app.post("/demo/agent/{agent_id}/prompt")
    async def prompt(agent_id: str, body: PromptBody) -> dict:
        return await conductor.prompt(agent_id, body.text)

    @app.post("/demo/rewind")
    async def rewind(body: Optional[RewindBody] = None) -> dict:
        body = body or RewindBody()
        return await conductor.rewind(body.turn, body.reason)

    @app.post("/demo/revert")
    async def revert(body: Optional[RevertBody] = None) -> dict:
        body = body or RevertBody()
        return await conductor.revert(body.commitment_id, body.reason)

    @app.post("/demo/branch")
    async def branch() -> dict:
        return await conductor.branch()

    @app.get("/demo/stream")
    async def stream() -> StreamingResponse:
        async def gen():
            q = conductor.subscribe()
            cursor = 0
            try:
                yield ": connected\n\n"
                while True:
                    events = await conductor.audit_snapshot()
                    for event in events[cursor:]:
                        yield _sse("audit", event)
                    cursor = len(events)
                    try:
                        msg = await asyncio.wait_for(q.get(), timeout=0.5)
                        yield _sse("message_event", msg)
                    except asyncio.TimeoutError:
                        pass
            finally:
                conductor.unsubscribe(q)

        return StreamingResponse(gen(), media_type="text/event-stream")

    return app
