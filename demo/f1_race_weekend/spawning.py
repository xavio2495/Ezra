"""Dynamic spawn/terminate driven by race events.

The fleet is emergent: always-on roles enter when the weekend starts; the rest
spawn when a named event fires (``fp1_start`` → telemetry + weather,
``inventory_drop`` → parts_shortage, etc.) and terminate when their work is done.
This is thin glue over the platform's ``SessionGraph.spawn_agent`` /
``terminate_agent`` — the demo's contribution is the event→role mapping, not new
runtime machinery.
"""

from __future__ import annotations

from demo.f1_race_weekend.agents.roles import (
    ROLES,
    AgentRole,
    always_on_roles,
    roles_for_event,
)
from ezra_core.schemas.session_graph import AgentRegistration
from ezra_core.session_graph import SessionGraph


class SpawnController:
    def __init__(self, graph: SessionGraph, roles: list[AgentRole] | None = None) -> None:
        self._graph = graph
        self._roles = roles if roles is not None else ROLES

    @property
    def active_ids(self) -> set[str]:
        return {a.agent_id for a in self._graph.active_agents}

    async def _spawn(self, role: AgentRole) -> AgentRegistration | None:
        if role.agent_id in self.active_ids:
            return None
        return await self._graph.spawn_agent(
            agent_id=role.agent_id,
            permission_scope=role.permission_scope,
            role=role.role,
        )

    async def spawn_always_on(self) -> list[AgentRegistration]:
        spawned = []
        for role in always_on_roles():
            reg = await self._spawn(role)
            if reg is not None:
                spawned.append(reg)
        return spawned

    async def handle_event(self, event_id: str) -> list[AgentRegistration]:
        """Spawn every conditional role bound to this event (idempotent)."""
        spawned = []
        for role in roles_for_event(event_id):
            reg = await self._spawn(role)
            if reg is not None:
                spawned.append(reg)
        return spawned

    async def terminate(self, agent_id: str) -> AgentRegistration:
        return await self._graph.terminate_agent(agent_id)
