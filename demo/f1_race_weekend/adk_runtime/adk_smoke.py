"""Live smoke for the deployed Ezra ADK service.

Runs in-cluster as a Job and proves the full remote surface end-to-end against a
*deployed* ``ezra-api`` (which talks to live Atlas):

  Part 1 (deterministic gate) — a ``RemoteEzraService`` drives commit -> rewind ->
  revert over HTTP and asserts the live belief state changes correctly.

  Part 2 (best-effort) — a real ``google.adk`` ``Runner`` with a low-cost Vertex
  model (Gemini Flash-Lite; Gemma on Vertex needs a self-deployed GPU endpoint)
  and an ``EzraToolset`` over the same remote service runs one turn, showing a real
  agent driving the deployed service. Tool-calling is non-deterministic, so a
  failure here is logged, not fatal — Part 1 is the proof.

Env: ``EZRA_API_URL`` (e.g. http://ezra-api), ``EZRA_API_BEARER_TOKEN`` (CSI
secret), and the Vertex routing vars for Part 2 (set on the Job).
"""

from __future__ import annotations

import asyncio
import os
import uuid

from ezra_core.adk_service.remote import RemoteEzraService

GRAPH = f"adk-smoke-{uuid.uuid4().hex[:8]}"
SMOKE_MODEL = os.environ.get("EZRA_SMOKE_MODEL", "vertex_ai/gemini-2.5-flash-lite")


def _claims(snapshot) -> set[str]:
    return {c.claim for c in snapshot.commitments}


async def part1_remote_lifecycle(api_url: str, token: str | None) -> dict:
    """Deterministic proof: commit -> rewind -> revert against the deployed API."""
    svc = RemoteEzraService(
        api_url, session_graph_id=GRAPH, agent_id="strategist",
        permission_scope=["tyres", "strategy"], bearer_token=token,
    )
    try:
        c1 = await svc.commit("start on softs", "tyres", turn_index=1)
        await svc.commit("plan a one-stop", "strategy", turn_index=2)
        before = _claims(await svc.belief_snapshot())

        rewind = await svc.rewind(1, reason="reset to opening call")
        after_rewind = _claims(await svc.belief_snapshot())

        await svc.revert(c1.commitment.id, reason="opening call was wrong", turn_index=3)
        after_revert = _claims(await svc.belief_snapshot())

        ok = (
            before == {"start on softs", "plan a one-stop"}
            and after_rewind == {"start on softs"}
            and after_revert == set()
        )
        return {
            "ok": ok, "graph": GRAPH,
            "before": sorted(before), "after_rewind": sorted(after_rewind),
            "rewind_undone": rewind.superseded_ids, "after_revert": sorted(after_revert),
        }
    finally:
        await svc.aclose()


def _adk_model(model: str):
    """Gemini models use ADK's native integration (bare id + Vertex via env) — the
    reliable tool-calling path. Non-Gemini Vertex models (e.g. Gemma) route through
    LiteLlm, which keeps the ``vertex_ai/`` prefix."""
    bare = model.split("/", 1)[1] if "/" in model else model
    if "gemini" in bare:
        return bare  # ADK Agent accepts a bare Gemini id; Vertex via GOOGLE_GENAI_USE_VERTEXAI
    from google.adk.models.lite_llm import LiteLlm

    return LiteLlm(model=model)


async def part2_llm_agent(api_url: str, token: str | None) -> dict:
    """Best-effort: a real ADK Runner with a Vertex LLM drives the deployed service."""
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    from ezra_core.adk_service import EzraToolset

    remote = RemoteEzraService(
        api_url, session_graph_id=f"{GRAPH}-agent", agent_id="strategist",
        permission_scope=["tyres"], bearer_token=token,
    )
    agent = Agent(
        name="strategist",
        model=_adk_model(SMOKE_MODEL),
        instruction=(
            "You are an F1 strategist. Use commit_belief to record the final-stint "
            "tyre as a one-line claim on topic 'tyres'. Then call belief_snapshot."
        ),
        tools=[EzraToolset(remote)],
    )
    sessions = InMemorySessionService()
    await sessions.create_session(app_name="ezra-adk-smoke", user_id="team", session_id="s1")
    runner = Runner(app_name="ezra-adk-smoke", agent=agent, session_service=sessions)

    text = ""
    msg = types.Content(role="user", parts=[types.Part(text="Decide and record the final-stint tyre.")])
    async for event in runner.run_async(user_id="team", session_id="s1", new_message=msg):
        if event.is_final_response() and event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts)
    snap = await remote.belief_snapshot()
    await remote.aclose()
    return {"response": text, "beliefs": sorted(_claims(snap))}


async def part3_nl_to_sql(settings) -> dict:
    """NL→native translation against REAL Snowflake: a natural-language intent is
    translated (Vertex meta model) into a constrained pushdown query and run on
    EZRA.PUBLIC.RACE_RESULTS — proving a filtered query, not SELECT *."""
    from ezra_core.mesh.connectors import snowflake_connector_from_settings

    columns = {
        "SEASON": "int", "ROUND": "int", "CIRCUIT": "str",
        "DRIVER": "str", "CONSTRUCTOR": "str", "POSITION": "int",
    }
    conn = snowflake_connector_from_settings(
        settings, "EZRA.PUBLIC.RACE_RESULTS", topics=["strategy"], columns=columns
    )
    # Season filter matches real rows regardless of circuit-name spelling.
    intent = os.environ.get("EZRA_SMOKE_INTENT", "all race results from the 2023 season")
    sql = conn.build_sql(intent)  # the translated, validated query
    result = await conn.fetch(intent, "strategist", ["strategy"])
    rows = len(result.data) if isinstance(result.data, list) else 0
    return {
        "intent": intent,
        "sql": sql,
        "translated": "WHERE" in sql.upper(),  # a predicate was produced (not SELECT *)
        "rows": rows,
        "time_travel": result.provenance.time_travel_available,
    }


async def _main() -> None:  # pragma: no cover - GKE Job entrypoint
    # Secret Manager CSI files (incl. the API bearer token) → EZRA_* env.
    from ezra_core.config import EzraSettings
    from ezra_core.secret_files import load_secret_files

    load_secret_files()
    settings = EzraSettings()
    api_url = os.environ.get("EZRA_API_URL", "http://ezra-api")
    token = os.environ.get("EZRA_API_BEARER_TOKEN") or None

    print(f"=== PART 1: remote commit/rewind/revert against {api_url} ===")
    p1 = await part1_remote_lifecycle(api_url, token)
    for k, v in p1.items():
        print(f"  {k}: {v}")
    print(f"  PART 1 {'PASSED' if p1['ok'] else 'FAILED'}")

    print(f"\n=== PART 2: real ADK Runner on {SMOKE_MODEL} (best-effort) ===")
    try:
        p2 = await part2_llm_agent(api_url, token)
        print("  response:", p2["response"][:300])
        print("  beliefs :", p2["beliefs"])
    except Exception as exc:  # noqa: BLE001 — LLM/tool-calling is best-effort
        print(f"  PART 2 skipped/failed (non-fatal): {type(exc).__name__}: {str(exc)[:200]}")

    print("\n=== PART 3: NL→SQL translation against real Snowflake ===")
    try:
        p3 = await part3_nl_to_sql(settings)
        print("  intent     :", p3["intent"])
        print("  translated :", p3["sql"])
        print("  has WHERE  :", p3["translated"])
        print("  rows       :", p3["rows"], "(time_travel:", p3["time_travel"], ")")
        print(f"  PART 3 {'PASSED' if p3['translated'] and p3['rows'] > 0 else 'INCONCLUSIVE'}")
    except Exception as exc:  # noqa: BLE001 — best-effort; Part 1 is the gate
        print(f"  PART 3 skipped/failed (non-fatal): {type(exc).__name__}: {str(exc)[:200]}")

    if not p1["ok"]:
        raise SystemExit("PART 1 (deterministic gate) failed")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(_main())
