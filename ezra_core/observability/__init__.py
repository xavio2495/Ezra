"""Observability — OpenTelemetry spans for the router pipeline, exported to
Arize Phoenix over OTLP/HTTP."""

from ezra_core.observability.tracer import (
    EzraTracer,
    RouterStep,
    tracer_from_settings,
)

__all__ = ["EzraTracer", "RouterStep", "tracer_from_settings"]
