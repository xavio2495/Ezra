# REST API

For systems that don't speak Python, Ezra Core exposes a FastAPI surface. All `/ezra/*` endpoints except `health` require a bearer token (`Authorization: Bearer <EZRA_API_BEARER_TOKEN>`).

```bash
curl -s https://ezra.example.com/ezra/health
curl -s -X POST https://ezra.example.com/ezra/belief/snapshot \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"session_graph_id":"race-weekend-monaco-2026","permission_scope":["tyres"]}'
```

## Endpoints

| Method | Path                       | Purpose                                                                          |
| ------ | -------------------------- | -------------------------------------------------------------------------------- |
| `GET`  | `/ezra/health`             | Liveness + which subsystems are wired.                                           |
| `POST` | `/ezra/context/assemble`   | Assemble the context an agent would see for an input (steps 3–6), no model call. |
| `POST` | `/ezra/belief/snapshot`    | Current scope-filtered active belief state.                                      |
| `POST` | `/ezra/belief/check`       | Detect a contradiction for a candidate claim.                                    |
| `POST` | `/ezra/mesh/query`         | Policy-gated federated query (403 if the scope is denied).                       |
| `POST` | `/ezra/commit`             | Commit a belief (detection + reconciliation + write-back).                       |
| `POST` | `/ezra/recall`             | Warm-tier semantic recall.                                                       |
| `POST` | `/ezra/rewind`             | Undo post-turn commitments on the live graph.                                    |
| `POST` | `/ezra/revert`             | Git-revert a single commitment.                                                  |
| `POST` | `/ezra/replay`             | Reconstruct belief state as-of a prior turn.                                     |
| `POST` | `/ezra/branch`             | Branch from a prior turn into a new graph.                                       |
| `POST` | `/ezra/branch/diff`        | Diff a branch against the original.                                              |
| `POST` | `/ezra/branch/run-forward` | Run a branch forward (501 when no forward step is configured).                   |

## Status codes

- **403** — the agent's permission scope denies a requested topic/source (enforced before any connector runs).
- **404** — unknown commitment / branch / graph.
- **501** — `branch/run-forward` when the generic surface has no agent step wired (running a branch forward re-executes agent turns the REST layer has no agents for).

## Notes

- The surface is backed by the same `EzraService` logic as the in-process SDK, via a `service_factory`.
- `RemoteEzraService` (httpx) duck-types `EzraService` over these endpoints, so an ADK `EzraToolset(RemoteEzraService(url))` drives a **deployed** Ezra exactly like an in-process one.
- The deployed composition root (`asgi.py`) builds the full runtime when Atlas is configured; the two-pass checker is off on the REST path by default to avoid per-commit embedding cost.
