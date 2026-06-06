# Ezra SDK examples

Runnable, self-contained examples of the Ezra Python SDK. Each one demonstrates a
single platform capability and runs **offline by default** (in-memory stores +
deterministic stand-ins for the model and the contradiction checker), so no
infrastructure is required.

## Run

```bash
uv run python -m examples.basic_chat
```

| Example | Shows |
|---|---|
| `basic_chat` | One agent, one turn through the full 8-step router |
| `multi_agent_session_graph` | Many agents on one graph; scope-filtered shared beliefs |
| `with_mongodb_source` | Federated MongoDB query (`time_travel_available=False`) |
| `with_snowflake_source` | Federated Snowflake query with native time-travel |
| `custom_reconciler` | Application-defined contradiction resolution (escalation) |
| `branching_replay` | Fork a graph at a prior turn, mutate, and diff |
| `cross_graph_inheritance` | A new graph inherits core memory from prior graphs |
| `replay_session` | Reconstruct the belief state as it stood at a prior turn |

## Against real backends

Every example is written as `async def run(ezra: Ezra)`, agnostic to how the
runtime was built. The `__main__` blocks use the offline harness
(`examples/_harness.py`); to run against real Atlas / Redis / Qdrant / Gemini,
build the runtime with `Ezra.from_env()` instead and call the same `run(ezra)`:

```python
import asyncio
from ezra_core.runtime import Ezra
from examples.basic_chat import run

ezra = Ezra.from_env()            # needs EZRA_* env (see .env.example)
print(asyncio.run(run(ezra)))
```

The examples are exercised by `tests/unit/test_examples.py` (each runs
end-to-end) and stress-tested under concurrency in
`tests/unit/test_examples_stress.py`.
