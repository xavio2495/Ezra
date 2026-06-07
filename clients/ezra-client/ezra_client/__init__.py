"""ezra-client — the slim SDK for driving a deployed Ezra over HTTP.

A standalone, dependency-light client (``httpx`` + ``pydantic``; ``google-adk``
optional) for talking to a deployed Ezra Core REST service. It carries no part of
the Ezra runtime — no Mongo/Qdrant/Redis/LLM — just the client surface and the
wire models.

    from ezra_client import RemoteEzraService, EzraToolset

    svc = RemoteEzraService(
        "https://ezra.example.com",
        session_graph_id="race-weekend",
        agent_id="strategist",
        permission_scope=["tyres", "strategy"],
        bearer_token="…",
    )
    await svc.commit("Start on softs.", "tyres", turn_index=1)

    # …or hand it to an ADK agent (needs `pip install ezra-client[adk]`):
    agent = Agent(name="strategist", model="gemini-2.5-flash",
                  tools=[EzraToolset(svc)])
"""

from ezra_client.errors import PolicyDeniedError, RemoteEzraError
from ezra_client.remote import RemoteEzraService
from ezra_client.tools import TurnCounter, ezra_adk_tools
from ezra_client.toolset import EzraToolset

__version__ = "0.1.0"

__all__ = [
    "RemoteEzraService",
    "EzraToolset",
    "ezra_adk_tools",
    "TurnCounter",
    "PolicyDeniedError",
    "RemoteEzraError",
    "__version__",
]
