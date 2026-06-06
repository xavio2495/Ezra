"""EzraService — the scope-bound façade an agent (ADK or any framework) holds,
plus the Google ADK integration surface: tools, an agent builder, a first-class
``EzraToolset`` (BaseToolset) and ``EzraMemoryService`` (BaseMemoryService).

The ADK pieces import ``google.adk`` lazily (only when constructed/built), so
importing this package never requires the optional ``agents`` dependency.
"""

from ezra_core.adk_service.adk import (
    TurnCounter,
    adk_model_id,
    build_ezra_agent,
    ezra_adk_tools,
)
from ezra_core.adk_service.memory_service import EzraMemoryService
from ezra_core.adk_service.service import EzraService
from ezra_core.adk_service.toolset import EzraToolset

__all__ = [
    "EzraService",
    "TurnCounter",
    "ezra_adk_tools",
    "build_ezra_agent",
    "adk_model_id",
    "EzraToolset",
    "EzraMemoryService",
]
