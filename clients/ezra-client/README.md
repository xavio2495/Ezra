# ezra-client

The slim SDK for driving a **deployed [Ezra](https://github.com/xavio2495/Ezra)**
multi-agent platform over HTTP. Dependency-light — `httpx` + `pydantic`, with
`google-adk` optional — and carries **no part of the Ezra runtime** (no
Mongo/Qdrant/Redis/LLM). For the full platform, install `ezra-core`.

## Install

```bash
pip install ezra-client          # core client
pip install "ezra-client[adk]"   # + the Google ADK toolset
```

## Use

```python
from ezra_client import RemoteEzraService

svc = RemoteEzraService(
    "https://ezra.example.com",
    session_graph_id="race-weekend",
    agent_id="strategist",
    permission_scope=["tyres", "strategy"],
    bearer_token="…",
)

# Commit a belief — the server runs two-pass contradiction detection +
# reconciliation; a scope violation raises PolicyDeniedError.
result = await svc.commit("Start on softs.", "tyres", turn_index=1)

# Inspect, time-travel, branch — the full scope-bound surface.
snap = await svc.belief_snapshot()
past = await svc.replay(turn=3)
branch = await svc.branch_from(turn=1, branch_id="what-if-wets")
```

### With a Google ADK agent

`EzraToolset` registers the full Ezra surface (recall · federated query · belief
snapshot/commit · revert/rewind/replay/branch) as managed ADK tools:

```python
from google.adk.agents import Agent
from ezra_client import RemoteEzraService, EzraToolset

agent = Agent(
    name="strategist",
    model="gemini-2.5-flash",
    instruction="You are the race strategist…",
    tools=[EzraToolset(svc)],
)
```

The same agent code drives Ezra in-process (`ezra_core`'s `EzraService`) or
remote (`RemoteEzraService`) — they share a method surface.

## Surface

`RemoteEzraService`: `recall`, `query`, `belief_snapshot`, `commit`, `revert`,
`rewind`, `replay`, `branch_from`, `aclose`.

Errors: `PolicyDeniedError` (HTTP 403 / scope denial), `RemoteEzraError` (other
4xx/5xx).
