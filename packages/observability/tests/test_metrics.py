import time
from collections.abc import Sequence
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk._logs import ReadableLogRecord
from opentelemetry.sdk._logs.export import LogRecordExporter, LogRecordExportResult
from opentelemetry.sdk.metrics.export import MetricExporter, MetricExportResult
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from hermes.observability.core.circuit_breaker import CircuitBreaker
from hermes.observability.logging.circuit_breaker import (
    CircuitBreakerLogRecordProcessor,
)
from hermes.observability.metrics.circuit_breaker import (
    CircuitBreakerMetricExporter,
)
from hermes.observability.metrics.guard import clean_labels
from hermes.observability.metrics.wrappers import (
    TelemetryCounter,
    TelemetryGauge,
    TelemetryHistogram,
)
from hermes.observability.tracing.circuit_breaker import (
    CircuitBreakerSpanExporter,
    CircuitBreakerSpanProcessor,
)


class MockSpanExporter(SpanExporter):
    def __init__(self, succeeds: bool = True) -> None:
        self.succeeds = succeeds
        self.export_calls = 0

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.export_calls += 1
        return SpanExportResult.SUCCESS if self.succeeds else SpanExportResult.FAILURE

    def shutdown(self, *args: Any, **kwargs: Any) -> None:
        pass


class MockLogExporter(LogRecordExporter):
    def __init__(self, succeeds: bool = True) -> None:
        self.succeeds = succeeds
        self.export_calls = 0

    def export(self, batch: Sequence[ReadableLogRecord]) -> LogRecordExportResult:
        self.export_calls += 1
        return LogRecordExportResult.SUCCESS if self.succeeds else LogRecordExportResult.FAILURE

    def shutdown(self, *args: Any, **kwargs: Any) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


class MockMetricExporter(MetricExporter):
    def __init__(self, succeeds: bool = True) -> None:
        super().__init__()
        self.succeeds = succeeds
        self.export_calls = 0

    def export(
        self, metrics_data: Any, timeout_millis: float = 10000, **kwargs: Any
    ) -> MetricExportResult:
        self.export_calls += 1
        return MetricExportResult.SUCCESS if self.succeeds else MetricExportResult.FAILURE

    def shutdown(self, *args: Any, **kwargs: Any) -> None:
        pass

    def force_flush(self, timeout_millis: float = 30000) -> bool:
        return True


def test_circuit_breaker_state_transitions() -> None:
    cb = CircuitBreaker(max_failures=3, cooldown=0.2)
    assert cb.state == "CLOSED"
    assert cb.can_attempt() is True

    # 1st failure
    cb.record_failure()
    assert cb.state == "CLOSED"
    assert cb.can_attempt() is True

    # 2nd failure
    cb.record_failure()
    assert cb.state == "CLOSED"
    assert cb.can_attempt() is True

    # 3rd failure - trips to OPEN
    cb.record_failure()
    assert cb.state == "OPEN"
    assert cb.can_attempt() is False

    # Immediate check - still open
    assert cb.can_attempt() is False

    # Wait for cooldown
    time.sleep(0.25)
    assert cb.can_attempt() is True  # transitioned to HALF-OPEN
    assert cb.state == "HALF-OPEN"

    # Test success resets to CLOSED
    cb.record_success()
    assert cb.state == "CLOSED"
    assert cb.failures == 0


def test_circuit_breaker_span_exporter() -> None:
    raw = MockSpanExporter(succeeds=False)
    cb_exporter = CircuitBreakerSpanExporter(raw, max_failures=2, cooldown=1.0)

    # 1st failure
    res = cb_exporter.export([])
    assert res == SpanExportResult.FAILURE
    assert raw.export_calls == 1

    # 2nd failure - trips circuit
    res = cb_exporter.export([])
    assert res == SpanExportResult.FAILURE
    assert raw.export_calls == 2

    # 3rd attempt - fails fast (does not call raw exporter)
    res = cb_exporter.export([])
    assert res == SpanExportResult.FAILURE
    assert raw.export_calls == 2


def test_circuit_breaker_span_processor_drop_mode() -> None:
    raw = MockSpanExporter(succeeds=True)
    processor = CircuitBreakerSpanProcessor(
        raw, max_queue_size=4, max_export_batch_size=4, schedule_delay_millis=10000
    )

    class DummySpan:
        def __init__(self, name: str) -> None:
            self.name = name

            class Context:
                trace_flags = type("Flags", (), {"sampled": True})()

            self.context = Context()

    span1: Any = DummySpan("span1")
    span2: Any = DummySpan("span2")
    span3: Any = DummySpan("span3")
    span4: Any = DummySpan("span4")
    span5: Any = DummySpan("span5")

    # enqueuing spans
    processor.on_end(span1)  # size=1
    processor.on_end(span2)  # size=2
    processor.on_end(span3)  # size=3
    assert len(processor._batch_processor._queue) == 3

    # size=4
    processor.on_end(span4)
    assert len(processor._batch_processor._queue) == 4

    # Enqueuing 5th span when queue size is at max (>= 85% of 4, which is 3.4)
    # This should drop the oldest (span1) and append span5.
    processor.on_end(span5)

    queue_list = list(processor._batch_processor._queue)
    assert len(queue_list) == 4
    names = [s.name for s in queue_list]
    assert "span1" not in names
    assert "span5" in names

    processor.shutdown()


def test_circuit_breaker_log_processor_drop_mode() -> None:
    raw = MockLogExporter(succeeds=True)
    processor = CircuitBreakerLogRecordProcessor(
        raw, max_queue_size=4, max_export_batch_size=4, schedule_delay_millis=10000
    )

    class DummyLogRecord:
        def __init__(self, body: str) -> None:
            # Mock log structure for translation
            class LogRecordObj:
                body = None
                context = None

            self.log_record = LogRecordObj()
            self.log_record.body = body
            self.resource = None
            self.instrumentation_scope = None
            self.limits = None

    log1 = DummyLogRecord("log1")
    log2 = DummyLogRecord("log2")
    log3 = DummyLogRecord("log3")
    log4 = DummyLogRecord("log4")
    log5 = DummyLogRecord("log5")

    # Enqueue logs
    processor.on_emit(log1)
    processor.on_emit(log2)
    processor.on_emit(log3)
    processor.on_emit(log4)
    assert len(processor._batch_processor._queue) == 4

    # 5th log triggers drop mode
    processor.on_emit(log5)

    queue_list = list(processor._batch_processor._queue)
    assert len(queue_list) == 4
    bodies = [log.log_record.body for log in queue_list]
    assert "log1" not in bodies
    assert "log5" in bodies

    processor.shutdown()


def test_circuit_breaker_metric_exporter_drop_mode() -> None:
    raw = MockMetricExporter(succeeds=False)
    # small queue size = 4
    cb_exporter = CircuitBreakerMetricExporter(raw, max_queue_size=4, max_failures=2, cooldown=1.0)

    # 1. Enqueue 4 batches
    assert cb_exporter.export("batch1") == MetricExportResult.SUCCESS
    assert cb_exporter.export("batch2") == MetricExportResult.SUCCESS
    assert cb_exporter.export("batch3") == MetricExportResult.SUCCESS
    assert cb_exporter.export("batch4") == MetricExportResult.SUCCESS
    assert cb_exporter._queue.qsize() == 4

    # 2. 5th batch triggers drop mode (drops "batch1" and adds "batch5")
    assert cb_exporter.export("batch5") == MetricExportResult.SUCCESS
    assert cb_exporter._queue.qsize() == 4

    batches = []
    while not cb_exporter._queue.empty():
        batches.append(cb_exporter._queue.get())

    assert "batch1" not in batches
    assert "batch5" in batches

    cb_exporter.shutdown()


def test_high_cardinality_guard_whitelist() -> None:
    # Whitelist is ["method", "status"]
    allowed = ["method", "status"]

    raw_labels = {"method": "GET", "status": "200", "user_id": "12345"}
    cleaned = clean_labels("my_metric", raw_labels, allowed_labels=allowed)

    # "user_id" is not whitelisted, so it should be dropped
    assert "method" in cleaned
    assert "status" in cleaned
    assert "user_id" not in cleaned


def test_high_cardinality_guard_redaction() -> None:
    # Setup test trace context
    tracer_provider = trace.get_tracer_provider()
    # Check if a real tracer provider is registered, otherwise use a temporary one
    if not hasattr(tracer_provider, "add_span_processor"):
        from opentelemetry.sdk.trace import TracerProvider

        tracer_provider = TracerProvider()

    span_exporter = InMemorySpanExporter()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))  # type: ignore

    tracer = tracer_provider.get_tracer("test-cardinality")

    with tracer.start_as_current_span("test-span") as active_span:
        from opentelemetry import context as ot_context

        token = ot_context.attach(trace.set_span_in_context(active_span))
        try:
            raw_labels = {
                "uuid_label": "123e4567-e89b-12d3-a456-426614174000",  # UUID
                "email_label": "user@domain.com",  # Email
                "long_id_label": "999999",  # Numeric ID >= 5 digits
                "short_id_label": "123",  # Short safe numeric label
                "user_id": "static-text",  # Key is user_id
            }
            cleaned = clean_labels("metric_test", raw_labels)

            assert cleaned["uuid_label"] == "generic_id"
            assert cleaned["email_label"] == "generic_id"
            assert cleaned["long_id_label"] == "generic_id"
            assert cleaned["short_id_label"] == "123"
            assert cleaned["user_id"] == "generic_id"

            # Check span attributes for redacted values
            attrs = active_span.attributes  # type: ignore
            assert (
                attrs["metric.redacted.metric_test.uuid_label"]
                == "123e4567-e89b-12d3-a456-426614174000"
            )
            assert attrs["metric.redacted.metric_test.email_label"] == "user@domain.com"
            assert attrs["metric.redacted.metric_test.long_id_label"] == "999999"
            assert attrs["metric.redacted.metric_test.user_id"] == "static-text"
        finally:
            ot_context.detach(token)


def test_metrics_wrappers_functional() -> None:
    counter = TelemetryCounter("test_counter", description="Test Counter")
    counter.inc(value=2, labels={"method": "GET"})

    gauge = TelemetryGauge("test_gauge", description="Test Gauge")
    gauge.set(10.0, labels={"queue": "tasks"})
    assert gauge._curr_values[frozenset([("queue", "tasks")])] == 10.0

    gauge.inc(2.5, labels={"queue": "tasks"})
    assert gauge._curr_values[frozenset([("queue", "tasks")])] == 12.5

    gauge.dec(1.5, labels={"queue": "tasks"})
    assert gauge._curr_values[frozenset([("queue", "tasks")])] == 11.0

    histogram = TelemetryHistogram("test_histogram", description="Test Histogram")
    with histogram.time(labels={"route": "/home"}):
        time.sleep(0.01)


def test_fastapi_http_metrics_instrumentation() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from opentelemetry import metrics as ot_metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader

    # Setup a test MeterProvider with InMemoryMetricReader
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])

    # Temporarily override the global meter provider for testing
    original_provider = ot_metrics.get_meter_provider()
    ot_metrics.set_meter_provider(provider)

    try:
        app = FastAPI()
        from hermes.observability import add_fastapi_observability

        add_fastapi_observability(app, enable_metrics=True)

        @app.get("/test-route")
        def route():
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/test-route")
        assert response.status_code == 200

        # Collect and verify metrics
        metrics_data = reader.get_metrics_data()
        assert metrics_data is not None

        # Verify that http_server_duration_seconds was recorded
        metric_names = []
        for resource_metric in metrics_data.resource_metrics:
            for scope_metric in resource_metric.scope_metrics:
                for metric in scope_metric.metrics:
                    metric_names.append(metric.name)

        # Check if HTTP server metric was registered
        http_metrics = [
            name for name in metric_names if "http.server" in name or "http_server" in name
        ]
        assert len(http_metrics) > 0
    finally:
        # Restore original provider
        ot_metrics.set_meter_provider(original_provider)
