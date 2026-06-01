"""OpenTelemetry tracing for Ezra, exported to Arize Phoenix over OTLP/HTTP.

``EzraTracer`` wraps an OTel ``Tracer`` with a ``span()`` context manager used to
instrument the eight router steps (and the meta-agents). When tracing is
disabled it returns a no-op span, so call sites stay unconditional and pay
nothing. Phoenix is just an OTLP collector — we point the standard OTLP/HTTP
exporter at ``EZRA_PHOENIX_ENDPOINT``; no Phoenix package import is needed in the
library (the Phoenix UI/server runs separately).

Tests build an ``EzraTracer`` over an in-memory span exporter (see
``EzraTracer.in_memory``) and assert on captured spans — no network, no Phoenix.
"""

from __future__ import annotations

from contextlib import contextmanager
from enum import Enum
from typing import Iterator, Optional

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import Tracer

_SERVICE_NAME = "ezra-core"


class RouterStep(str, Enum):
    """Span names for the eight-step router pipeline (HANDOFF §8-step router)."""

    PARSE = "router.parse"
    POLICY = "router.policy"
    BELIEF_CHECK = "router.belief_check"
    HYDRATE = "router.hydrate"
    FETCH = "router.fetch"
    ASSEMBLE = "router.assemble"
    LLM = "router.llm"
    WRITE_BACK = "router.write_back"


class _NoopSpan:
    """Stand-in returned when tracing is disabled — accepts attributes, no-ops."""

    def set_attribute(self, key: str, value: object) -> None:  # noqa: D401
        pass

    def set_attributes(self, attributes: dict) -> None:
        pass

    def add_event(self, name: str, attributes: Optional[dict] = None) -> None:
        pass


class EzraTracer:
    def __init__(self, provider: Optional[TracerProvider] = None, *, enabled: bool = True) -> None:
        self._enabled = enabled and provider is not None
        self._provider = provider
        self._tracer: Optional[Tracer] = (
            provider.get_tracer(_SERVICE_NAME) if self._enabled else None
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    @contextmanager
    def span(self, name: object, **attributes: object) -> Iterator[object]:
        span_name = name.value if isinstance(name, RouterStep) else str(name)
        if not self._enabled:
            yield _NoopSpan()
            return
        assert self._tracer is not None
        with self._tracer.start_as_current_span(span_name) as span:
            for key, value in attributes.items():
                span.set_attribute(key, value)
            yield span

    # -- factories -------------------------------------------------------- #
    @classmethod
    def disabled(cls) -> "EzraTracer":
        return cls(provider=None, enabled=False)

    @classmethod
    def in_memory(cls) -> tuple["EzraTracer", InMemorySpanExporter]:
        """A tracer backed by an in-memory exporter — for tests."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        return cls(provider, enabled=True), exporter


def tracer_from_settings(settings) -> EzraTracer:
    """Build the production tracer: OTLP/HTTP exporter → Phoenix. Returns a
    disabled tracer when ``EZRA_TRACING_ENABLED`` is false."""
    if not settings.tracing_enabled:
        return EzraTracer.disabled()

    # Imported lazily so the OTLP/grpc-free path stays light and import-safe.
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )

    provider = TracerProvider()
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.phoenix_endpoint))
    )
    return EzraTracer(provider, enabled=True)
