"""Build a real ``google.adk`` Agent for an F1 role, wired to Ezra.

``build_adk_agent`` turns an :class:`AgentRole` + its scope-bound ``EzraService``
into an ADK ``Agent`` whose instruction is the existing parameterised role prompt
and whose tools are the Ezra-bound functions from :mod:`ezra_tools`. The model is
the configured Gemini agent model (``EZRA_LLM_MODEL``); ADK takes the bare model
id (no ``gemini/`` litellm prefix).
"""

from __future__ import annotations

from demo.f1_race_weekend.adk_runtime.ezra_tools import TurnCounter, build_tools
from demo.f1_race_weekend.agents.roles import AgentRole, build_system_prompt
from ezra_core.adk_service.service import EzraService


def _adk_model_id(llm_model: str) -> str:
    """litellm uses 'gemini/gemini-2.5-flash'; ADK/genai wants 'gemini-2.5-flash'."""
    return llm_model.split("/", 1)[1] if "/" in llm_model else llm_model


def build_adk_agent(
    role: AgentRole,
    service: EzraService,
    *,
    llm_model: str,
    api_key: str = "",
    turns: TurnCounter | None = None,
    events: list | None = None,
):
    """Create the ADK Agent for ``role``. Returns ``(agent, turns)``.

    ADK talks to Gemini through google-genai (not litellm), which reads the key
    from ``GOOGLE_API_KEY``; we mirror Ezra's ``EZRA_LLM_API_KEY`` into it.
    """
    import os

    from google.adk.agents import Agent

    # On Vertex (vertex_ai/ model), ADK/google-genai authenticates via ADC using the
    # GOOGLE_GENAI_USE_VERTEXAI / GOOGLE_CLOUD_PROJECT / _LOCATION env (set on the
    # GKE Job) — do NOT set an API key. Otherwise use the AI Studio key.
    if not llm_model.startswith("vertex_ai/") and api_key and not os.environ.get("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = api_key

    turns = turns or TurnCounter()
    instruction = build_system_prompt(role) + (
        "\n\nUse your tools: recall prior context, fetch_federated for live data "
        "(only within your remit), and commit_belief to record each decision. "
        "Commit decisions as short, specific one-line claims."
    )
    agent = Agent(
        name=role.agent_id,
        model=_adk_model_id(llm_model),
        instruction=instruction,
        tools=build_tools(service, turns, events),
    )
    return agent, turns
