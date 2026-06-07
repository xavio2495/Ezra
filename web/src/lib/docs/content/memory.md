# Three-Tier Memory

Ezra manages memory across three tiers modelled on the hardware memory hierarchy — each a different time scale, backed by a different store, all scope-filtered per agent.

| Tier     | Analog    | Latency  | Holds                                            | Backing store                   |
| -------- | --------- | -------- | ------------------------------------------------ | ------------------------------- |
| **Hot**  | CPU cache | ~0 ms    | Active turn, pinned beliefs, fetched mesh result | Redis (per-agent hash)          |
| **Warm** | RAM       | 5–15 ms  | Compressed prior turns, topic summaries          | Qdrant (graph + scope filtered) |
| **Cold** | SSD       | 20–50 ms | Episodic, semantic, procedural, belief history   | MongoDB Atlas                   |

## Hot — Redis

One Redis hash per agent holds the recent turns (a capped ring buffer), pinned beliefs, and the latest mesh result. Because each agent owns its key, the hot tier is **O(1) per agent** — adding agents adds rows, not iterations.

## Warm — Qdrant

Compressed prior-turn and topic summaries, recalled by semantic similarity to the current input and filtered server-side by `session_graph_id`, then in Python by scope and TTL. Summaries past their TTL are evicted by the lifecycle meta-agent.

## Cold — MongoDB Atlas

Four sub-stores share one Atlas client:

| Sub-store               | Loading                           | Notes                                    |
| ----------------------- | --------------------------------- | ---------------------------------------- |
| **Episodic**            | by session-graph / timestamp      | Time-windowed event memory               |
| **Semantic — core**     | always, at agent spawn, for scope | The always-needed facts                  |
| **Semantic — archival** | per turn, by vector similarity    | **Atlas Vector Search**                  |
| **Procedural**          | by intent pattern                 | Inferred behavioural rules               |
| **Belief history**      | append-only, queryable            | The compliance artifact — never compacts |

### Core vs. archival semantic memory

**Core** facts load at every spawn for the agent's scope (institutional knowledge it always needs). **Archival** facts are the long tail: on every turn, the router embeds the input and pulls the most-similar archival facts via Atlas `$vectorSearch`, scope-filtered. Each recall bumps the fact's access count; once it crosses a threshold the learning meta-agent **promotes it to core**, so frequently-needed knowledge graduates into the always-loaded set.

```python
# Per-turn archival recall (run inside router step 4):
facts = await semantic_store.recall_archival(
    "how long do the medium tyres last?",
    user_id="team-ezra",
    scope_topics={"tyres", "strategy"},
    limit=3,
)
```

The vector index is created with `MongoSemanticStore.ensure_vector_index(num_dimensions)` at wiring/ingest time (sized to the embedder — `gemini-embedding-001` is 3072-dim; Vertex `text-embedding-005` is 768-dim).

## Cross-graph inheritance

A new session graph can hydrate core semantic memory from any number of prior graphs:

```python
graph = await ezra.create_session_graph(
    session_graph_id="race-weekend-imola-2026",
    inherits_from=["race-weekend-monaco-2026", "race-weekend-bahrain-2026"],
)
```

Inherited core facts load at spawn, scope-filtered. Belief _history_ is never inherited — only semantic core (and, optionally, procedural rules).
