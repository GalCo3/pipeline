from enum import StrEnum


class CircuitBreakerState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF-OPEN"


class MetricUnit(StrEnum):
    """Standardized UCUM units of measure for metrics."""

    SECONDS = "s"
    MILLISECONDS = "ms"
    MICROSECONDS = "us"
    BYTES = "By"
    KILOBYTES = "KBy"
    MEGABYTES = "MBy"
    PERCENT = "%"
    DIMENSIONLESS = "1"
