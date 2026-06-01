"""Data-driven F1 agent roles (replaces nine hand-written agent modules).

Each role is an ``AgentRole``: an id, a human role string, a permission scope (a
set of topic tags), a one-line mandate, and how it enters the fleet — always-on,
or conditionally spawned by a named race event. Scopes are chosen so the demo's
permission-denial beat is real: ``logistics`` covers ``[parts, supplier,
calendar]`` and is genuinely denied an ``aero`` fetch.

Fleet shape for the Monaco demo:
  - 4 always-on:        race_strategy, tyre_engineer, aero_rd, logistics
  - +2 at fp1_start:    telemetry_analyst, weather_model   (4 → 6)
  - +1 at inventory_drop: parts_shortage                   (6 → 7)
  - +1 at security_alert: security
  - +1 at fia_event:    press_coordinator
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from demo.f1_race_weekend.prompts.role_template import render_prompt

TEAM = "Team Ezra"
EVENT = "Monaco Grand Prix weekend"


class AgentRole(BaseModel):
    agent_id: str
    role: str
    permission_scope: list[str] = Field(default_factory=list)
    mandate: str = ""
    always_on: bool = True
    # Event id that triggers a conditional spawn (None for always-on roles).
    spawn_event: Optional[str] = None


ROLES: list[AgentRole] = [
    AgentRole(
        agent_id="race_strategy",
        role="Race Strategist",
        permission_scope=["strategy", "tyres"],
        mandate="Own the race plan: stint lengths, compounds, pit windows.",
    ),
    AgentRole(
        agent_id="tyre_engineer",
        role="Tyre Engineer",
        permission_scope=["tyres"],
        mandate="Track compound wear and temperatures; advise tyre choice.",
    ),
    AgentRole(
        agent_id="aero_rd",
        role="Aero R&D Engineer",
        permission_scope=["aero"],
        mandate="Own downforce targets and wing configuration.",
    ),
    AgentRole(
        agent_id="logistics",
        role="Logistics Coordinator",
        permission_scope=["parts", "supplier", "calendar"],
        mandate="Manage parts flow, supplier contracts, and the weekend calendar.",
    ),
    AgentRole(
        agent_id="telemetry_analyst",
        role="Telemetry Analyst",
        permission_scope=["telemetry"],
        mandate="Stream live car telemetry and surface anomalies.",
        always_on=False,
        spawn_event="fp1_start",
    ),
    AgentRole(
        agent_id="weather_model",
        role="Weather Modeller",
        permission_scope=["weather"],
        mandate="Forecast track conditions and rain windows.",
        always_on=False,
        spawn_event="fp1_start",
    ),
    AgentRole(
        agent_id="parts_shortage",
        role="Parts Shortage Responder",
        permission_scope=["parts"],
        mandate="React to inventory shortfalls and assess race feasibility.",
        always_on=False,
        spawn_event="inventory_drop",
    ),
    AgentRole(
        agent_id="security",
        role="Paddock Security",
        permission_scope=["security", "crew"],
        mandate="Manage crew clearances and paddock access alerts.",
        always_on=False,
        spawn_event="security_alert",
    ),
    AgentRole(
        agent_id="press_coordinator",
        role="Press Coordinator",
        permission_scope=["press", "media"],
        mandate="Coordinate media response to FIA events.",
        always_on=False,
        spawn_event="fia_event",
    ),
]

_BY_ID = {r.agent_id: r for r in ROLES}


def role_by_id(agent_id: str) -> AgentRole:
    return _BY_ID[agent_id]


def always_on_roles() -> list[AgentRole]:
    return [r for r in ROLES if r.always_on]


def conditional_roles() -> list[AgentRole]:
    return [r for r in ROLES if not r.always_on]


def roles_for_event(event_id: str) -> list[AgentRole]:
    return [r for r in ROLES if r.spawn_event == event_id]


def build_system_prompt(role: AgentRole, *, team: str = TEAM, event: str = EVENT) -> str:
    return render_prompt(
        role=role.role,
        team=team,
        event=event,
        scope=role.permission_scope,
        mandate=role.mandate,
    )
