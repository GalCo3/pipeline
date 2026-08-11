from collections.abc import Sequence
from typing import Any

from opentelemetry.sdk._logs import ReadableLogRecord
from opentelemetry.sdk._logs.export import (
    BatchLogRecordProcessor,
    LogRecordExporter,
    LogRecordExportResult,
)

from hermes.observability.core.circuit_breaker import CircuitBreaker
from hermes.observability.utils import enforce_queue_drop_mode


class CircuitBreakerLogExporter(LogRecordExporter):
    """Wraps a LogRecordExporter with circuit breaker protection."""

    def __init__(
        self, exporter: LogRecordExporter, max_failures: int = 3, cooldown: float = 30.0
    ) -> None:
        self._exporter = exporter
        self._cb = CircuitBreaker(max_failures, cooldown)

    def export(self, batch: Sequence[ReadableLogRecord]) -> LogRecordExportResult:
        if not self._cb.can_attempt():
            return LogRecordExportResult.FAILURE

        try:
            result = self._exporter.export(batch)
        except Exception:
            result = LogRecordExportResult.FAILURE

        if result == LogRecordExportResult.SUCCESS:
            self._cb.record_success()
        else:
            self._cb.record_failure()
        return result

    def shutdown(self) -> None:
        self._exporter.shutdown()  # type: ignore[no-untyped-call]

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        try:
            return self._exporter.force_flush(timeout_millis)
        except Exception:
            return False


class CircuitBreakerLogRecordProcessor(BatchLogRecordProcessor):
    """Subclass of BatchLogRecordProcessor implementing memory-safe drop mode at 85% capacity."""

    def on_emit(self, log_record: Any) -> None:
        enforce_queue_drop_mode(self._batch_processor)
        super().on_emit(log_record)
