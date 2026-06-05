"""Real Google ADK multi-agent runtime over the Ezra platform.

This package is the live counterpart to the deterministic ``race_weekend_demo``:
each F1 role becomes a real ``google.adk`` ``Agent`` whose tools are bound to a
per-agent :class:`ezra_core.adk_service.EzraService`. Agents reason with Gemini,
commit beliefs through Ezra, and genuine contradictions surface from their actual
outputs and are resolved by the real reconciler — nothing is hand-scripted.

It lives under ``demo/`` (not ``ezra_core/``) because it is an example consumer of
the platform, not part of the runtime.
"""
