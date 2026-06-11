"""Demo Conductor — the all-in-one live-demo service (claude-docs/demo-dashboard-plan.md).

Runs the F1 fleet in-process over a real :class:`ezra_core.runtime.Ezra`, drives a
real Ezra turn per presenter chat prompt, and streams two SSE channels to the
``ezra-dashboard`` UI: ``message_event`` (agent turn outputs → the chat panes) and
``audit`` (the persisted :class:`AuditEvent` feed → the right-column visualizers).
A demo harness that *uses* the platform — deliberately not part of ``ezra-api``.
"""

from demo.conductor.app import create_app

__all__ = ["create_app"]
