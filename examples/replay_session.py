"""replay_session — reconstruct the belief state as it stood at a prior turn.

Replay is time-aware: a commitment superseded at turn 5 is still active in a
snapshot reconstructed at turn 3. Here a plan made at turn 1 is later revised at
turn 5; replaying turn 3 shows the original plan, while the current snapshot shows
the revision.
"""

from __future__ import annotations

import asyncio

from ezra_core.runtime import Ezra

from examples._harness import build_offline_ezra


async def run(ezra: Ezra) -> dict:
    graph = await ezra.create_session_graph(session_graph_id="replay-demo")
    strategist = await ezra.spawn_agent(
        graph, agent_id="strategist", permission_scope=["tyres"]
    )

    first = await strategist.write_back("Start on softs", "tyres", turn_index=1)
    revised = await strategist.write_back("Revised: switch to mediums", "tyres", turn_index=5)
    # At turn 5 the original plan is superseded by the revision.
    await ezra.belief_store.supersede(first.id, revised.id)

    at_turn_3 = await strategist.replay(3)  # before the revision existed
    now = await strategist.belief_snapshot()  # current state
    return {
        "at_turn_3": [c.claim for c in at_turn_3.commitments],
        "now": [c.claim for c in now.commitments],
    }


async def _demo() -> None:
    ezra = build_offline_ezra()
    try:
        result = await run(ezra)
        print("as of turn 3 :", result["at_turn_3"], "(original plan still active)")
        print("now          :", result["now"], "(revised plan)")
    finally:
        await ezra.aclose()


if __name__ == "__main__":
    asyncio.run(_demo())
