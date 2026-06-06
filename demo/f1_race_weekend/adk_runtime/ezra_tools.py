"""ADK tools bound to one F1 agent's :class:`EzraService`.

The tool-building surface is platform-owned (``ezra_core.adk_service.adk``); this
module just re-exports it under the names the demo already uses, so the F1 demo
consumes the same integration any ADK app would. See
:func:`ezra_core.adk_service.ezra_adk_tools` for the tool definitions.
"""

from __future__ import annotations

from ezra_core.adk_service.adk import TurnCounter, ezra_adk_tools as build_tools

__all__ = ["TurnCounter", "build_tools"]
