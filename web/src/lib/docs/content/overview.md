# Overview

Ezra is an **enterprise multi-agent platform** for production AI. A fleet of agents — of any size, spawning and terminating dynamically based on what the operation needs — share federated memory, federated data access, and a versioned audit trail of every commitment any agent made.

It is built for the case where one organisation needs many specialised agents acting in parallel, under permission boundaries, on time-critical work — and where per-agent decision latency must stay flat as the fleet grows.

## The two jobs

Ezra does two distinct things at enterprise scale.

**Data federation (the mesh).** Connect to fragmented enterprise sources. Enforce permissions via a policy engine that inherits the user's identity or the agent's scope. Translate intent into _pushdown_ queries that execute at the storage layer and return typed, provenance-tagged summaries — never raw data dumps.

**Context management (the runtime).** Decide what each agent in the fleet sees on every call. Manage what persists, what compresses, and what gets evicted across three memory tiers. Catch belief contradictions _across_ the fleet and reconcile them before the model is called. Replay any session at any historical moment — and branch into counterfactual futures.

Most tools solve one or the other, for a single agent. Ezra does both, for any number of agents, as one platform.

## What makes it different

- **Cross-agent belief reconciliation** — when two agents disagree on the same topic, a two-pass detector catches it and one of four strategies resolves it, before the wrong action is taken.
- **Branching replay** — reconstruct any prior state, _mutate_ it, spawn agents that never existed, run forward, and diff against reality.
- **Federated pushdown query** — MongoDB, Snowflake, BigQuery, Atlas Stream Processing, REST — the database does the math; the agent gets a typed summary.
- **Per-agent permission inheritance** — scope is enforced at the federation layer, not left to the model to self-censor.
- **Flat per-agent latency** — adding agents adds rows, not iterations (see [Architecture](/docs/architecture)).

## When to use Ezra

Ezra fits any domain with a dynamic fleet of scoped agents over federated data: incident response across infra / security / comms, financial operations across treasury / compliance / research, supply chain across procurement / logistics / inventory, or the reference demo — **Formula 1 race-weekend operations**, where telemetry, strategy, aero, parts, and press agents spawn and terminate across a weekend and contradict each other in real time.

## Where to go next

- [Quickstart](/docs/quickstart) — install, wire the backends, run your first agent.
- [Architecture](/docs/architecture) — the dual-layer model, session graphs, and how latency stays flat.
- [The 8-Step Router](/docs/router) — what happens on every agent turn.
