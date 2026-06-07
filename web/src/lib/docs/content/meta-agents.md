# Meta-Agents & Observability

Two meta-agents run alongside the fleet, **enabled by default** and **asynchronous / non-blocking**. The runtime is correct without them, but degraded — trust scores stop evolving, archival compaction stops, lifecycle transitions stop.

## Learning meta-agent

Runs after router step 8, every turn. Three jobs:

1. **Memory write scoring** — of the facts extracted from a turn, only those confident enough are persisted to the cold tier; low-confidence candidates are dropped rather than polluting semantic memory.
2. **Core/archival promotion** — an archival fact whose access count crosses `core_promotion_access_count` (default 3) graduates to **core**, so it loads at every spawn instead of only on a similarity match.
3. **Trust updates** — after a reconciliation, the winner's per-topic trust moves toward 1.0 and the loser's toward 0.0, _damped_ so a single event nudges rather than swings.

It can also extract durable facts from raw turn text via the LLM (`extract_facts`) when no explicit candidates are supplied. Wired into `Router.run_turn` (via `learning=` + `user_id=`), it returns a `LearningReport` on the `TurnResult`.

```python
result = await svc.complete("…")          # learning pass runs after the response
print(result.learning_report)             # persisted / promoted / trust updates
```

## Lifecycle meta-agent

Runs on a schedule (default every 5 min per active graph, hourly per closed graph):

- **State transitions** — active → closed (last agent terminated) → archived (idle past the graph's threshold).
- **Archival compaction** — on closed → archived, compact episodic/warm and review semantic facts; **belief history is left verbatim — the compliance artifact never compacts.**
- **Retention enforcement** — tombstone commitments older than the graph's `belief_retention_days` (None = infinite).
- **GDPR tombstones** — apply redaction tombstones requested via the API (append-only; the audit hash stays valid, the content becomes unreadable).

```python
report = await ezra.run_lifecycle_tick("race-weekend-monaco-2026")
```

Per-graph configuration is read off the `SessionGraph` record itself, so one agent serves graphs with different retention policies.

## Observability — OpenTelemetry → Phoenix

Ezra emits structured OpenTelemetry spans. The router wraps each of its eight steps (`router.parse`, `router.policy`, … `router.write_back`), and **each meta-agent owns its own span** — `meta.learning` (with persisted / promoted / trust-update counts) and `meta.lifecycle` (with transition / tombstoned-count / evicted-warm). Spans export over OTLP/HTTP to **Arize Phoenix** (or any OTLP collector); Phoenix runs separately — there's no Phoenix import in the library.

```bash
EZRA_TRACING_ENABLED=true
EZRA_PHOENIX_ENDPOINT="http://phoenix:6006/v1/traces"
```

In tests, `EzraTracer.in_memory()` captures spans for assertions; `EzraTracer.disabled()` is a zero-cost no-op so call sites stay unconditional.
