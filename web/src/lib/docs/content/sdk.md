# Python SDK

The SDK has two objects: **`Ezra`** — the shared runtime you build once — and **`EzraService`** — a scope-bound handle you get per agent.

## `Ezra` — the runtime

```python
from ezra_core.runtime import Ezra

ezra = Ezra.from_env()                       # build from EZRA_* env
ezra = Ezra.from_settings(settings, build_checker=True)
```

`from_env` / `from_settings` wire the real backends (Atlas cold tier, Redis hot, Qdrant warm, the two-pass checker, the litellm adapter, the branch manager, both meta-agents, the tracer). `build_checker=False` skips the heavy local NLI model where the two-pass checker isn't needed. For unit tests, construct `Ezra(...)` directly with in-memory components.

| Method                                                                                                   | Purpose                                               |
| -------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| `create_session_graph(session_graph_id, *, merge_strategy, custom_resolver, inherits_from, description)` | Create a graph (the unit that binds N agents).        |
| `spawn_agent(graph, *, agent_id, permission_scope, role, user_id, mesh)`                                 | Register an agent → returns its `EzraService`.        |
| `on_contradiction(callback)`                                                                             | Register the manual-mode callback (decorator).        |
| `run_lifecycle_tick(session_graph_id)`                                                                   | Run one scheduled lifecycle pass → `LifecycleReport`. |
| `branch_manager`                                                                                         | The `BranchManager` for replay/branching.             |
| `aclose()`                                                                                               | Drain and close all backends.                         |

```python
graph = await ezra.create_session_graph(
    session_graph_id="race-weekend-monaco-2026",
    merge_strategy="highest_trust",
    inherits_from=["race-weekend-bahrain-2026"],
)
svc = await ezra.spawn_agent(
    graph,
    agent_id="race_strategy",
    permission_scope=["tyres", "strategy"],
    role="Race strategy engineer.",
    user_id="team-ezra",
    mesh=snowflake_connector,          # optional federated source
)
```

## `EzraService` — the per-agent handle

Scope-bound: every call is enforced against the agent's `permission_scope`.

| Method                                                                     | Purpose                                                           |
| -------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `complete(user_input, *, system_prompt="")`                                | Run a full 8-step turn → `TurnResult(response, context, …)`.      |
| `commit(claim, topic, *, turn_index, type="decision", value, trust_score)` | Commit a belief with detection + reconciliation → `CommitResult`. |
| `write_back(claim, topic, *, turn_index, …)`                               | Append a commitment without the model call.                       |
| `belief_snapshot()`                                                        | Current scope-filtered active beliefs → `BeliefSnapshot`.         |
| `belief_check(claim, topic)`                                               | Detect a contradiction for a candidate claim.                     |
| `recall(query, *, limit=5)`                                                | Warm-tier semantic recall → `list[WarmSummary]`.                  |
| `query(query, *, topics, as_of)`                                           | Policy-gated federated fetch → `MeshResult`.                      |
| `replay(turn)`                                                             | Reconstruct belief state as-of a prior turn.                      |
| `rewind(turn, *, reason)`                                                  | Undo post-turn commitments on the live graph → `RewindResult`.    |
| `revert(commitment_id, *, reason, turn_index)`                             | Git-revert a single commitment.                                   |
| `branch_from(turn, *, branch_id)`                                          | Fork a branch from a prior turn.                                  |

```python
result = await svc.complete("What tyre for the final stint?", system_prompt="You strategise.")
print(result.response)

commit = await svc.commit("Start on mediums, one-stop.", "tyres", turn_index=1)
if commit.contradiction:
    print("resolved by", commit.resolution.merge_strategy_used)

data = await svc.query("current pit-lane delta", topics=["strategy"])
print(data.provenance.source, data.provenance.time_travel_available)
```

## Framework integration

Ezra is framework-agnostic. ADK agents use the `EzraToolset` / `EzraMemoryService` (see [Deployment](/docs/deployment)); LangGraph / LangChain / custom agents use this Python SDK directly; everything else uses the [REST API](/docs/rest-api). A `RemoteEzraService` mirrors the `EzraService` surface over HTTP, so an ADK toolset can drive a _deployed_ Ezra identically to in-process.
