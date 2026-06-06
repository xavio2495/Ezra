"""EzraToolset — a first-class ADK BaseToolset exposing the full Ezra surface.

Verifies the toolset is a real ``BaseToolset``, surfaces all Ezra tools as
``FunctionTool`` instances (including the git-like rewind/revert/replay/branch),
and that the tools drive the bound service.
"""

from datetime import datetime, timezone

import pytest

pytest.importorskip("google.adk")

from ezra_core.adk_service import EzraToolset  # noqa: E402
from ezra_core.adk_service.service import EzraService  # noqa: E402
from ezra_core.belief.store import InMemoryBeliefStore  # noqa: E402


def _service():
    return EzraService(
        session_graph_id="g",
        agent_id="strategist",
        permission_scope=["tyres"],
        belief_store=InMemoryBeliefStore(),
    )


def test_toolset_is_a_real_adk_base_toolset():
    from google.adk.tools.base_toolset import BaseToolset

    ts = EzraToolset(_service())
    assert isinstance(ts, BaseToolset)


async def test_get_tools_exposes_the_full_ezra_surface_as_function_tools():
    from google.adk.tools import FunctionTool

    ts = EzraToolset(_service())
    tools = await ts.get_tools()
    assert all(isinstance(t, FunctionTool) for t in tools)
    assert {t.name for t in tools} == {
        "recall", "belief_snapshot", "fetch_federated", "commit_belief",
        "revert_belief", "rewind_beliefs", "replay_beliefs", "branch_beliefs",
    }


async def test_get_tools_is_cached():
    ts = EzraToolset(_service())
    assert await ts.get_tools() is await ts.get_tools()


async def test_rewind_tool_drives_the_service():
    svc = _service()
    ts = EzraToolset(svc)
    tools = {t.name: t for t in await ts.get_tools()}

    await svc.write_back("opening call", "tyres", turn_index=1)
    await svc.write_back("revised call", "tyres", turn_index=5)
    out = await tools["rewind_beliefs"].func(turn=1, reason="reset")
    assert out["status"] == "success"
    assert out["rewound_to_turn"] == 1
    active = {c.claim for c in (await svc.belief_snapshot()).commitments}
    assert active == {"opening call"}


async def test_revert_tool_drops_a_single_belief():
    svc = _service()
    ts = EzraToolset(svc)
    tools = {t.name: t for t in await ts.get_tools()}

    c = await svc.write_back("bad call", "tyres", turn_index=1)
    await svc.write_back("good call", "tyres", turn_index=2)
    out = await tools["revert_belief"].func(commitment_id=c.id, reason="wrong")
    assert out["status"] == "success"
    active = {c.claim for c in (await svc.belief_snapshot()).commitments}
    assert active == {"good call"}
