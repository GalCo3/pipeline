import logging
from collections.abc import Generator
from typing import Any

import pytest
from opentelemetry import trace
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from hermes.observability.core import configure_telemetry


@pytest.fixture(autouse=True)
def reset_telemetry() -> Generator[None]:
    """Resets and shuts down tracer and logger providers to clean up background worker threads."""
    yield
    tp: Any = trace.get_tracer_provider()
    if hasattr(tp, "shutdown"):
        tp.shutdown()
    lp: Any = get_logger_provider()
    if hasattr(lp, "shutdown"):
        lp.shutdown()

    import opentelemetry._logs as ot_logs
    import opentelemetry.trace as ot_trace
    from opentelemetry.util._once import Once

    ot_trace._TRACER_PROVIDER = None
    ot_trace._TRACER_PROVIDER_SET_ONCE = Once()

    ot_logs._internal._LOGGER_PROVIDER = None
    ot_logs._internal._LOGGER_PROVIDER_SET_ONCE = Once()

    # Clean up LoggingHandler from root logger
    root_logger = logging.getLogger()
    for h in root_logger.handlers[:]:
        if h.__class__.__name__ in ("LoggingHandler", "StructuredOTelLoggingHandler"):
            root_logger.removeHandler(h)


def test_configure_telemetry_successful() -> None:
    service_name = "test-service"
    configure_telemetry(
        service_name=service_name, is_production=False, otlp_endpoint="localhost:4317"
    )

    # 1. Verify TracerProvider registration and Service Name Resource Attribute
    tracer_provider = trace.get_tracer_provider()
    assert isinstance(tracer_provider, TracerProvider)
    assert tracer_provider.resource.attributes["service.name"] == service_name

    # 2. Verify LoggerProvider registration and Resource Attribute
    logger_provider = get_logger_provider()
    assert isinstance(logger_provider, LoggerProvider)
    assert logger_provider.resource.attributes["service.name"] == service_name


def test_telemetry_captures_in_memory() -> None:
    service_name = "in-memory-service"
    configure_telemetry(
        service_name=service_name, is_production=False, otlp_endpoint="localhost:4317"
    )

    # Access current providers
    tracer_provider = trace.get_tracer_provider()
    assert isinstance(tracer_provider, TracerProvider)

    logger_provider = get_logger_provider()
    assert isinstance(logger_provider, LoggerProvider)

    # Attach in-memory exporters for testing
    span_exporter = InMemorySpanExporter()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))

    log_exporter = InMemoryLogRecordExporter()
    logger_provider.add_log_record_processor(SimpleLogRecordProcessor(log_exporter))

    # Emit a span
    tracer = trace.get_tracer("test-tracer")
    with tracer.start_as_current_span("test-span"):
        pass

    # Emit a log via standard logging
    logger = logging.getLogger("test-logging-route")
    logger.warning("Test warning log")

    # Verify spans and logs were captured
    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "test-span"

    log_records = log_exporter.get_finished_logs()
    assert len(log_records) > 0
    # Ensure our warning log was captured
    warning_logs = [r for r in log_records if r.log_record.body == "Test warning log"]
    assert len(warning_logs) == 1
    assert warning_logs[0].log_record.severity_text == "WARN"


def test_configure_telemetry_fail_safe() -> None:
    # Passing an invalid endpoint (or empty values) should not crash the call
    configure_telemetry(service_name="", is_production=True, otlp_endpoint="")
    # It fails safely and doesn't raise exceptions


def test_log_trace_correlation(capsys: pytest.CaptureFixture[str]) -> None:
    import json

    from hermes.observability import configure_logging, get_logger

    # 1. Setup telemetry and logging in JSON production mode
    configure_telemetry("trace-corr-test", is_production=False)
    configure_logging(is_production=True)
    logger = get_logger("trace-corr-test")

    # A. Test emitting log outside active span context
    logger.info("Log outside trace")
    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert "trace_id" not in data
    assert "span_id" not in data
    assert "parent_span_id" not in data

    # B. Test emitting log inside active span context
    tracer = trace.get_tracer("test-tracer")
    with tracer.start_as_current_span("parent-span") as parent:
        logger.info("Log inside parent span")
        captured = capsys.readouterr()
        data_parent = json.loads(captured.out.strip())

        expected_trace_id = format(parent.get_span_context().trace_id, "032x")
        expected_span_id = format(parent.get_span_context().span_id, "016x")

        assert data_parent["trace_id"] == expected_trace_id
        assert data_parent["span_id"] == expected_span_id
        assert "parent_span_id" not in data_parent

        # C. Test emitting log inside nested child span context
        with tracer.start_as_current_span("child-span") as child:
            logger.info("Log inside child span")
            captured = capsys.readouterr()
            data_child = json.loads(captured.out.strip())

            expected_child_span_id = format(child.get_span_context().span_id, "016x")

            assert data_child["trace_id"] == expected_trace_id
            assert data_child["span_id"] == expected_child_span_id
            assert data_child["parent_span_id"] == expected_span_id


def test_structured_telemetry_captures_in_memory() -> None:
    from hermes.observability import configure_logging, get_logger

    service_name = "structured-service"
    configure_logging(is_production=True)
    configure_telemetry(
        service_name=service_name, is_production=False, otlp_endpoint="localhost:4317"
    )

    logger_provider = get_logger_provider()
    log_exporter = InMemoryLogRecordExporter()
    logger_provider.add_log_record_processor(SimpleLogRecordProcessor(log_exporter))  # type: ignore

    logger = get_logger("test-structured-otel")
    logger.info("Structured log message", user_id="123", custom_arg="val")

    log_records = log_exporter.get_finished_logs()
    assert len(log_records) > 0

    # Find the record
    target_record = None
    for record in log_records:
        if record.log_record.body == "Structured log message":
            target_record = record.log_record
            break

    assert target_record is not None
    attrs = target_record.attributes
    assert attrs is not None
    assert attrs["logger"] == "test-structured-otel"
    assert attrs["level"] == "INFO"
    # Whitelisted fields or custom fields in metadata
    assert attrs["metadata"]["user_id"] == "123"  # type: ignore
    assert attrs["metadata"]["custom_arg"] == "val"  # type: ignore
