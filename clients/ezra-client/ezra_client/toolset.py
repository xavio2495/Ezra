"""EzraToolset — a first-class Google ADK ``BaseToolset`` over Ezra.

Registering this on an ADK ``Agent`` (``tools=[EzraToolset(service)]``) exposes
the full Ezra surface as managed ADK tools. ``service`` is any object with the
scope-bound method surface — typically a :class:`ezra_client.RemoteEzraService`
against a deployed Ezra. ``google.adk`` is imported lazily, so this module is
importable without the optional ``adk`` extra installed (only constructing an
``EzraToolset`` requires it).
"""

from __future__ import annotations

from typing import Optional

from ezra_client.tools import TurnCounter, ezra_adk_tools


class EzraToolset:
    """An ADK ``BaseToolset`` exposing the full Ezra surface for one agent.

    Subclasses ``google.adk.tools.BaseToolset`` at construction time (lazy import)
    so the module stays importable without ``google-adk`` installed.
    """

    def __new__(cls, *args, **kwargs):
        from google.adk.tools.base_toolset import BaseToolset

        if not issubclass(cls, BaseToolset):
            cls = type("EzraToolset", (EzraToolset, BaseToolset), {})
        return object.__new__(cls)

    def __init__(self, service, *, turns: Optional[TurnCounter] = None, events=None) -> None:
        from google.adk.tools.base_toolset import BaseToolset

        BaseToolset.__init__(self)
        self._service = service
        self._turns = turns or TurnCounter()
        self._events = events
        self._tools = None

    async def get_tools(self, readonly_context=None) -> list:
        """Return the Ezra tools as ADK ``FunctionTool`` instances (cached).

        Async because ADK's ``BaseToolset.get_tools`` is a coroutine — ADK awaits
        it when collecting an agent's tools.
        """
        from google.adk.tools import FunctionTool

        if self._tools is None:
            self._tools = [
                FunctionTool(fn)
                for fn in ezra_adk_tools(self._service, self._turns, events=self._events)
            ]
        return self._tools

    async def close(self) -> None:  # ADK lifecycle hook; nothing to release.
        return None
