import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from opentelemetry import context, metrics

from hermes.observability.metrics.guard import clean_labels
from hermes.observability.types import MetricUnit


class TelemetryCounter:
    """Simplifies the OpenTelemetry Counter SDK with clean labels and high cardinality guard."""

    def __init__(
        self,
        name: str,
        description: str = "",
        unit: MetricUnit | str = "",
        allowed_labels: list[str] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.unit = unit
        self.allowed_labels = allowed_labels
        self._meter = metrics.get_meter("observability")
        self._counter = self._meter.create_counter(
            name=name,
            description=description,
            unit=unit,
        )

    def inc(self, value: int = 1, labels: dict[str, Any] | None = None) -> None:
        cleaned = clean_labels(self.name, labels, self.allowed_labels)
        current_ctx = context.get_current()
        self._counter.add(value, cleaned, context=current_ctx)


class TelemetryGauge:
    """Wraps OpenTelemetry UpDownCounter to implement a standard Gauge with inc(),
    dec(), and set()."""

    def __init__(
        self,
        name: str,
        description: str = "",
        unit: MetricUnit | str = "",
        allowed_labels: list[str] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.unit = unit
        self.allowed_labels = allowed_labels
        self._meter = metrics.get_meter("observability")
        self._up_down_counter = self._meter.create_up_down_counter(
            name=name,
            description=description,
            unit=unit,
        )
        self._curr_values: dict[frozenset[tuple[str, str]], float] = {}
        self._lock = threading.Lock()

    def inc(self, value: float = 1.0, labels: dict[str, Any] | None = None) -> None:
        cleaned = clean_labels(self.name, labels, self.allowed_labels)
        key = frozenset(cleaned.items())
        current_ctx = context.get_current()
        with self._lock:
            self._curr_values[key] = self._curr_values.get(key, 0.0) + value
            self._up_down_counter.add(value, cleaned, context=current_ctx)

    def dec(self, value: float = 1.0, labels: dict[str, Any] | None = None) -> None:
        cleaned = clean_labels(self.name, labels, self.allowed_labels)
        key = frozenset(cleaned.items())
        current_ctx = context.get_current()
        with self._lock:
            self._curr_values[key] = self._curr_values.get(key, 0.0) - value
            self._up_down_counter.add(-value, cleaned, context=current_ctx)

    def set(self, value: float, labels: dict[str, Any] | None = None) -> None:
        cleaned = clean_labels(self.name, labels, self.allowed_labels)
        key = frozenset(cleaned.items())
        current_ctx = context.get_current()
        with self._lock:
            current = self._curr_values.get(key, 0.0)
            diff = value - current
            self._curr_values[key] = value
            if diff != 0:
                self._up_down_counter.add(diff, cleaned, context=current_ctx)


class TelemetryHistogram:
    """Wraps OpenTelemetry Histogram and provides a time() context manager."""

    def __init__(
        self,
        name: str,
        description: str = "",
        unit: MetricUnit | str = "",
        allowed_labels: list[str] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.unit = unit
        self.allowed_labels = allowed_labels
        self._meter = metrics.get_meter("observability")
        self._histogram = self._meter.create_histogram(
            name=name,
            description=description,
            unit=unit,
        )

    def record(self, amount: float, labels: dict[str, Any] | None = None) -> None:
        cleaned = clean_labels(self.name, labels, self.allowed_labels)
        current_ctx = context.get_current()
        self._histogram.record(amount, cleaned, context=current_ctx)

    @contextmanager
    def time(self, labels: dict[str, Any] | None = None) -> Generator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.record(duration, labels)
