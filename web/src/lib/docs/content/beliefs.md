# Beliefs & Reconciliation

Every factual commitment by any agent is tracked, versioned, and attributed in a shared, append-only belief store. When agents disagree, Ezra catches it **before the model call** and resolves it with a configurable strategy.

## Two-pass contradiction detection

Detection runs at router step 3 as a non-negotiable two-pass pipeline:

1. **First pass — embedding similarity.** A cheap cosine filter (`> 0.85`) over same-topic commitments identifies candidate pairs.
2. **Second pass — NLI.** A Natural Language Inference classifier (DeBERTa-v3, local) labels each candidate `entailment | neutral | contradiction`. Only `contradiction` (at/above the confidence threshold) invokes the reconciler.

Embedding similarity alone fails both ways, which is why the second pass is mandatory:

- _Embedding-close but not contradictory_ — "the tyre is soft" vs "the tyre is firm".
- _Embedding-distant but contradictory_ — "recommend supplier A" vs "recommend supplier B" (caught because they share a topic, then confirmed by NLI).

On GKE a no-torch **Gemini-backed** checker stands in for the local DeBERTa model, keeping the same two-pass shape.

## Four reconciliation strategies

Set per session graph via `merge_strategy`:

| Strategy          | Behaviour                                                                                                              |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `last_write_wins` | Newest commitment supersedes. Simple, predictable. **Default.**                                                        |
| `highest_trust`   | Per-topic agent trust scores break the tie; trust evolves via the learning meta-agent.                                 |
| `manual`          | Contradiction surfaced to a callback; the call blocks until resolved (with a timeout → fallback to `last_write_wins`). |
| `custom`          | Application provides a resolver `Callable[[Contradiction, ResolveContext], Resolution]`.                               |

```python
graph = await ezra.create_session_graph(
    session_graph_id="…",
    merge_strategy="highest_trust",
)
```

## Manual mode — the `@ezra.on_contradiction` decorator

Register a callback that decides each contradiction. The reconciler hands it a `ContradictionEvent` and blocks on its decision (up to the manual-resolution timeout). Agents spawned after registration pick it up.

```python
@ezra.on_contradiction
async def resolve(event):
    # Surface to an ops console / Slack / PagerDuty, then decide.
    decision = await ops_console.escalate(event)
    return decision  # "accept_new" | "keep_existing"
```

With no callback registered, a `manual` graph falls back to `manual_no_callback_fallback` (accept-new).

## Custom resolvers

```python
async def my_resolver(c, ctx):
    if c.topic == "compliance" and ctx.regulatory_mode == "strict":
        return Resolution.keep_existing(c)         # compliance always wins
    if {c.existing_agent_id, c.new_agent_id} == {"a", "b"}:
        return Resolution.escalate(c)              # always escalate this pair
    return Resolution.fallback_to(strategy="highest_trust")

graph = await ezra.create_session_graph(
    session_graph_id="…", merge_strategy="custom", custom_resolver=my_resolver,
)
```

## Committing & inspecting

```python
result = await svc.commit("Start on mediums.", "tyres", turn_index=1)
# result.contradiction / result.resolution are populated when one fired.

snap = await svc.belief_snapshot()          # current scope-filtered active beliefs
print([c.claim for c in snap.commitments])
```

Every commitment carries `agent_id`; the history records which agent committed what, when, and what it superseded. The store is **append-only** — supersession and GDPR redaction flip flags / write tombstones, never delete, so the audit chain stays intact. See [Branching Replay](/docs/branching) for reconstructing and forking prior states.
