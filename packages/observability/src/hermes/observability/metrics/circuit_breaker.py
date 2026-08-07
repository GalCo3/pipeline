import contextlib
import queue
import threading
from typing import Any

from opentelemetry.sdk.metrics.export import MetricExporter, MetricExportResult

from hermes.observability.constants import QUEUE_DROP_THRESHOLD
from hermes.observability.core.circuit_breaker import CircuitBreaker


class CircuitBreakerMetricExporter(MetricExporter):
    """MetricExporter wrapper that adds circuit breaker protection and a bounded queue."""

    def __init__(
        self,
        exporter: MetricExporter,
        max_queue_size: int = 1000,
        max_failures: int = 3,
        cooldown: float = 30.0,
    ) -> None:
        """Initializes the exporter with circuit breaker protection and an async worker thread."""
        preferred_temporality = getattr(exporter, "_preferred_temporality", None)
        preferred_aggregation = getattr(exporter, "_preferred_aggregation", None)
        super().__init__(
            preferred_temporality=preferred_temporality,
            preferred_aggregation=preferred_aggregation,
        )
        self._exporter = exporter
        self._queue: queue.Queue[Any] = queue.Queue(max_queue_size)
        self._max_queue_size = max_queue_size
        self._cb = CircuitBreaker(max_failures, cooldown)
        self._shutdown = False
        self._lock = threading.Lock()

        # Spawn the background worker thread to process queued exports asynchronously
        self._worker_thread = threading.Thread(
            target=self._worker,
            name="OtelCircuitBreakerMetricExporterWorker",
            daemon=True,
        )
        self._worker_thread.start()

    def export(
        self,
        metrics_data: Any,
        timeout_millis: float = 10000,
        **kwargs: Any,
    ) -> MetricExportResult:
        """Enqueues metric data asynchronously to avoid blocking the main thread."""
        if self._shutdown:
            return MetricExportResult.FAILURE

        # Discard the oldest item if the queue is approaching capacity to avoid blocking
        with contextlib.suppress(Exception):
            if self._queue.qsize() >= QUEUE_DROP_THRESHOLD * self._max_queue_size:
                with contextlib.suppress(queue.Empty):
                    self._queue.get_nowait()

        try:
            self._queue.put_nowait(metrics_data)
            return MetricExportResult.SUCCESS
        except queue.Full:
            return MetricExportResult.FAILURE

    def _worker(self) -> None:
        """Loop executed by background thread to pull from queue and export metrics."""
        while not self._shutdown:
            try:
                metrics_data = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            # Skip transmission if the circuit breaker is open (healthy state is false)
            if not self._cb.can_attempt():
                self._queue.task_done()
                continue

            try:
                result = self._exporter.export(metrics_data)
            except Exception:
                result = MetricExportResult.FAILURE

            # Update the circuit breaker state based on the result
            if result == MetricExportResult.SUCCESS:
                self._cb.record_success()
            else:
                self._cb.record_failure()
            self._queue.task_done()

    def shutdown(self, timeout_millis: float = 30000, **kwargs: Any) -> None:
        """Gracefully shuts down the background worker and the underlying exporter."""
        self._shutdown = True
        with contextlib.suppress(Exception):
            self._worker_thread.join(timeout=5.0)
        self._exporter.shutdown(timeout_millis=timeout_millis, **kwargs)

    def force_flush(self, timeout_millis: float = 30000) -> bool:
        """Flushes any pending records in the underlying exporter."""
        if hasattr(self._exporter, "force_flush"):
            try:
                return self._exporter.force_flush(timeout_millis)
            except Exception:
                return False
        return True
