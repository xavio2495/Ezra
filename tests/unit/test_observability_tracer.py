from ezra_core.observability.tracer import EzraTracer, RouterStep, tracer_from_settings


class FakeSettings:
    def __init__(self, enabled):
        self.tracing_enabled = enabled
        self.phoenix_endpoint = "http://localhost:6006/v1/traces"


def test_disabled_tracer_is_noop_and_records_nothing():
    tracer = EzraTracer.disabled()
    assert tracer.enabled is False
    with tracer.span(RouterStep.LLM, agent_id="strategist") as span:
        span.set_attribute("model", "gemini")  # must not raise


def test_in_memory_tracer_records_named_router_spans():
    tracer, exporter = EzraTracer.in_memory()
    with tracer.span(RouterStep.BELIEF_CHECK, agent_id="parts"):
        pass
    with tracer.span("router.llm", model="gemini-2.0-flash"):
        pass

    spans = exporter.get_finished_spans()
    names = [s.name for s in spans]
    assert "router.belief_check" in names
    assert "router.llm" in names


def test_span_attributes_are_attached():
    tracer, exporter = EzraTracer.in_memory()
    with tracer.span(RouterStep.FETCH, agent_id="telemetry", connector="bigquery"):
        pass

    span = exporter.get_finished_spans()[0]
    assert span.attributes["agent_id"] == "telemetry"
    assert span.attributes["connector"] == "bigquery"


def test_tracer_from_settings_disabled_when_flag_off():
    tracer = tracer_from_settings(FakeSettings(enabled=False))
    assert tracer.enabled is False
