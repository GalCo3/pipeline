from enum import StrEnum


class MessageStatus(StrEnum):
    """Standardized message processing status labels for telemetry metrics."""

    SUCCESS = "success"
    INDEXED = "indexed"
    UPDATED = "updated"
    DELETED = "deleted"
    SKIPPED = "skipped"
    NOT_FOUND = "not_found"
    ERROR = "error"


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
