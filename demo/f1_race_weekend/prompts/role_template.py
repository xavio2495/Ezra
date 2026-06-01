"""Single parameterised prompt template, role-filled per agent.

The compressed Session-5 scope replaces nine bespoke prompt files with one
template whose slots (role, scope, mandate) are filled from each agent's role
definition. This keeps every agent's framing consistent and makes the "fleet of
agents" feel like one operation rather than nine disconnected bots.
"""

from __future__ import annotations

ROLE_PROMPT_TEMPLATE = """\
You are the {role} for {team} during the {event}.
Your remit (permission scope): {scope}.
{mandate}

Operating rules:
- Only commit claims that fall within your remit; defer anything outside it.
- State decisions as short, specific commitments (one line each).
- When you rely on federated data, name the source.
"""


def render_prompt(*, role: str, team: str, event: str, scope: list[str], mandate: str) -> str:
    return ROLE_PROMPT_TEMPLATE.format(
        role=role,
        team=team,
        event=event,
        scope=", ".join(scope) if scope else "(global)",
        mandate=mandate,
    )
