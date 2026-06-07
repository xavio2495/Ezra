# Branching Replay

Replay reconstructs what any agent knew at any prior moment — its scope, the active belief state across the fleet, and the data available. **Branching replay** goes further: at any prior moment you can _modify_ state and let the system run forward, turning Ezra from an audit tool into a counterfactual-exploration tool. No other memory/agent platform ships this.

## Replay a prior state

```python
snapshot = await svc.replay(turn=15)   # belief state as-of turn 15, scope-filtered
```

Because the belief store is append-only and supersession is time-aware, a fact superseded at turn 20 is still active in a turn-15 snapshot.

## Branch, mutate, run forward, diff

The full branching API is on `ezra.branch_manager`. A branch is itself a first-class session graph: the parent's state as-of the branch turn is reconstructed and seeded into the branch's own belief store, re-keyed.

```python
bm = ezra.branch_manager

# 1 · branch from a prior moment
branch = await bm.branch_from(
    session_graph_id="incident-2026-05-20",
    turn=15,
    branch_id="what-if-db-specialist-earlier",
)

# 2 · mutate state — anything is fair game
await bm.mutate_belief(
    branch_id=branch.branch_id,
    agent_id="triage",
    new_claim="primary suspicion is connection-pool exhaustion",
    topic="diagnosis",
)

# spawn an agent the original never had (counterfactual)
await bm.spawn_agent(
    branch_id=branch.branch_id,
    agent_id="db_specialist",
    permission_scope=["database", "telemetry"],
    # In the original, db_specialist spawned at T+8min; here it exists from turn 16.
)

# 3 · run the branch forward — your step coroutine executes each turn
await bm.run_forward(branch_id=branch.branch_id, until_turn=25, step=run_one_turn)

# 4 · compare branch vs. reality
diff = await bm.diff_branches(
    original="incident-2026-05-20",
    branch="what-if-db-specialist-earlier",
    from_turn=15,
)
```

### `spawn_agent` inside a branch

`branch.spawn_agent` registers a new `AgentRegistration` on the **branch's own** session-graph record (not the parent's), so a counterfactual can introduce an agent that never existed in reality. `run_forward` then drives it and `diff_branches` attributes its commitments. `at_turn` defaults to the branch point + 1; a duplicate `agent_id` raises, and an unknown branch raises.

`run_forward(step=…)` takes an injected per-turn coroutine, so _how_ a turn executes (a real router turn in production, a stub in tests) stays the caller's concern — the manager stays agnostic.

## What it enables

- **Audit** — "what if the weather agent had committed earlier?" Run the branch, compare to reality.
- **Forward planning** — "what if procurement recommended supplier B?" See downstream effects on logistics and operations.
- **Training & evaluation** — replay a whole session against a different model; diff responses turn-by-turn.
- **Compliance** — "could a different policy decision have prevented this?" Mutate policy state, run forward, diff.

## Git-like rewind & revert

Ezra also ships append-only, auditable history operations on the **live** graph (distinct from branching, which forks into a new graph):

```python
await svc.rewind(turn=15, reason="reset to the opening call")   # undo post-turn commitments
await svc.revert(commitment_id, reason="opening call was wrong", turn_index=20)
```

`rewind_to_turn` undoes every post-turn commitment on the live graph and reactivates anything they had superseded, so the live active set equals the turn-15 reconstruction. `revert` git-reverts a single commitment. Both append marker records — the row is kept, the operation is itself auditable.
