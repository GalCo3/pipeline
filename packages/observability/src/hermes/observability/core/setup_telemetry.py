import logging

from opentelemetry import metrics, trace
from opentelemetry._logs import LogRecord, set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

from hermes.observability.constants import DEFAULT_HISTOGRAM_BOUNDARIES
from hermes.observability.logging.circuit_breaker import (
    CircuitBreakerLogExporter,
    CircuitBreakerLogRecordProcessor,
)
from hermes.observability.metrics.circuit_breaker import (
    CircuitBreakerMetricExporter,
)
from hermes.observability.tracing.circuit_breaker import (
    CircuitBreakerSpanExporter,
    CircuitBreakerSpanProcessor,
)
from hermes.observability.utils import (
    is_channel_insecure,
    is_production_environment,
    resolve_otlp_endpoint,
)


class StructuredOTelLoggingHandler(LoggingHandler):
    """
    Custom OpenTelemetry LoggingHandler that parses dictionary log records
    produced by structlog, setting the main string body and extracting structured attributes.
    """

    def _translate(self, record: logging.LogRecord) -> LogRecord:
        log_record = super()._translate(record)

        if isinstance(record.msg, dict):
            event_dict = record.msg
            if "message" in event_dict:
                log_record.body = event_dict["message"]
            elif "event" in event_dict:
                log_record.body = event_dict["event"]

            attrs = dict(log_record.attributes) if log_record.attributes else {}
            for key, val in event_dict.items():
                if key not in ("message", "event"):
                    attrs[key] = val
            log_record.attributes = attrs
        return log_record


def _setup_tracer(resource: Resource, endpoint: str, insecure: bool) -> None:
    """Configures global OTel TracerProvider and registers OTLP gRPC span exporter
    wrapped in a Circuit Breaker."""
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)

    raw_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=insecure)
    cb_exporter = CircuitBreakerSpanExporter(raw_exporter)

    tracer_provider.add_span_processor(CircuitBreakerSpanProcessor(cb_exporter))


def _setup_logger(resource: Resource, endpoint: str, insecure: bool) -> None:
    """Configures global OTel LoggerProvider, OTLP gRPC log exporter and root logging
    handler wrapped in a Circuit Breaker."""
    logger_provider = LoggerProvider(resource=resource)
    set_logger_provider(logger_provider)

    raw_exporter = OTLPLogExporter(endpoint=endpoint, insecure=insecure)
    cb_exporter = CircuitBreakerLogExporter(raw_exporter)

    logger_provider.add_log_record_processor(CircuitBreakerLogRecordProcessor(cb_exporter))

    logging_handler = StructuredOTelLoggingHandler(
        level=logging.NOTSET, logger_provider=logger_provider
    )
    logging.getLogger().addHandler(logging_handler)


def _setup_metrics(resource: Resource, endpoint: str, insecure: bool) -> None:
    """Configures global OTel MeterProvider, OTLP gRPC metric exporter and views
    wrapped in a Circuit Breaker."""
    latency_view = View(
        instrument_type=metrics.Histogram,
        aggregation=ExplicitBucketHistogramAggregation(boundaries=DEFAULT_HISTOGRAM_BOUNDARIES),
    )

    raw_exporter = OTLPMetricExporter(endpoint=endpoint, insecure=insecure)
    cb_exporter = CircuitBreakerMetricExporter(raw_exporter)

    metric_reader = PeriodicExportingMetricReader(cb_exporter)

    meter_provider = MeterProvider(
        resource=resource, metric_readers=[metric_reader], views=[latency_view]
    )
    metrics.set_meter_provider(meter_provider)


def configure_telemetry(
    service_name: str,
    is_production: bool | None = None,
    otlp_endpoint: str | None = None,
) -> None:
    """
    Bootstraps the OpenTelemetry SDK TracerProvider, LoggerProvider, and MeterProvider.
    Pushes traces, logs, and metrics natively via OTLP gRPC to the local sidecar collector.
    Fails silently to ensure telemetry failures never crash the host application.
    """
    try:
        resource = Resource.create({"service.name": service_name})
        is_prod = is_production if is_production is not None else is_production_environment()
        endpoint = resolve_otlp_endpoint(otlp_endpoint)
        insecure = is_channel_insecure(endpoint, is_prod)

        _setup_tracer(resource, endpoint, insecure)
        _setup_logger(resource, endpoint, insecure)
        _setup_metrics(resource, endpoint, insecure)
    except Exception as exc:
        logging.getLogger(__name__).warning("Failed to bootstrap OpenTelemetry telemetry: %s", exc)
