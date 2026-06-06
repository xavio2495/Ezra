"""branching_replay — fork a graph at a prior turn, mutate it, and diff.

Branching replay explores counterfactuals: reconstruct a graph's belief state as
it stood at turn N, fork it into a new branch (itself a first-class session
graph), inject a different decision, then diff the branch against the original to
see exactly what diverged.
"""

from __future__ import annotations

import asyncio

from ezra_core.runtime import Ezra

from examples._harness import build_offline_ezra


async def run(ezra: Ezra) -> dict:
    graph = await ezra.create_session_graph(session_graph_id="branch-demo")
    strategist = await ezra.spawn_agent(
        graph, agent_id="strategist", permission_scope=["tyres"]
    )
    await strategist.write_back("Plan: soft-to-hard one-stop", "tyres", turn_index=1)
    await strategist.write_back("Confirm: stay on softs to the end", "tyres", turn_index=2)

    mgr = ezra.branch_manager
    branch = await mgr.branch_from(
        session_graph_id="branch-demo", turn=1, branch_id="what-if-wets"
    )
    # In the branch, turn 2 goes differently:
    await mgr.mutate_belief(
        branch_id="what-if-wets",
        agent_id="strategist",
        new_claim="Switch to wets at lap 43",
        topic="tyres",
        turn_index=2,
    )
    diff = await mgr.diff_branches(original="branch-demo", branch="what-if-wets", from_turn=1)
    return {"branch_id": branch.branch_id, "diverged": diff.diverged_commitments}


async def _demo() -> None:
    ezra = build_offline_ezra()
    try:
        result = await run(ezra)
        print("branch:", result["branch_id"])
        for d in result["diverged"]:
            print(f"  topic {d['topic']}:")
            print("    only in original:", d["only_in_original"])
            print("    only in branch  :", d["only_in_branch"])
    finally:
        await ezra.aclose()


if __name__ == "__main__":
    asyncio.run(_demo())
