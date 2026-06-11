# Ezra Live Demo Dashboard

The presenter-facing UI for the [Demo Conductor](../demo/conductor/): six interactive
agent chat panes driving real per-agent Ezra turns, beside real-time visualizers
(context/commitment graph, data-access ledger, audit log) rendered **only** from the
platform's persisted `AuditEvent` feed.

SvelteKit · Svelte 5 runes · Tailwind v4 · shadcn-svelte · `@xyflow/svelte`.

## Develop

```bash
# 1. the conductor (from the repo root; offline mode, port 8090)
docker compose run --rm --no-deps -p 8090:8090 app uv run --frozen python -m demo.conductor

# 2. this app, pointed at it
VITE_CONDUCTOR_URL=http://localhost:8090 npm run dev
```

Click **▷ Start** to spawn the fleet, prompt agents through the pre-filled briefings
(race_strategy first, tyre_engineer second to fire the contradiction on cue), and
drive Rewind / Revert / Branch from the control strip.

`npm run check` must stay at 0 errors. In production the conductor serves this app
from its own origin on GKE (no `VITE_CONDUCTOR_URL` needed).
