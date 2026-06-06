"""EzraService — the scope-bound façade an agent (ADK or any framework) holds,
plus the Google ADK integration surface (tools + agent builder).

``adk`` lazily imports ``google.adk`` only inside :func:`build_ezra_agent`, so
importing this package never requires the optional ``agents`` dependency.
"""

from ezra_core.adk_service.adk import (
    TurnCounter,
    adk_model_id,
    build_ezra_agent,
    ezra_adk_tools,
)
from ezra_core.adk_service.service import EzraService

__all__ = [
    "EzraService",
    "TurnCounter",
    "ezra_adk_tools",
    "build_ezra_agent",
    "adk_model_id",
]
