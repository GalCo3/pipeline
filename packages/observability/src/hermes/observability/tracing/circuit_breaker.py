from collections.abc import Sequence

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult

from hermes.observability.core.circuit_breaker import CircuitBreaker
from hermes.observability.utils import enforce_queue_drop_mode


class CircuitBreakerSpanExporter(SpanExporter):
    """Wraps a SpanExporter with circuit breaker protection."""

    def __init__(
        self, exporter: SpanExporter, max_failures: int = 3, cooldown: float = 30.0
    ) -> None:
        self._exporter = exporter
        self._cb = CircuitBreaker(max_failures, cooldown)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        if not self._cb.can_attempt():
            return SpanExportResult.FAILURE

        try:
            result = self._exporter.export(spans)
        except Exception:
            result = SpanExportResult.FAILURE

        if result == SpanExportResult.SUCCESS:
            self._cb.record_success()
        else:
            self._cb.record_failure()
        return result

    def shutdown(self) -> None:
        self._exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._exporter.force_flush(timeout_millis)


class CircuitBreakerSpanProcessor(BatchSpanProcessor):
    """Subclass of BatchSpanProcessor implementing memory-safe drop mode at 85% capacity."""

    def on_end(self, span: ReadableSpan) -> None:
        enforce_queue_drop_mode(self._batch_processor)
        super().on_end(span)
