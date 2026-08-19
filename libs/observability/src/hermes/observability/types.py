from enum import StrEnum


class MessageStatus(StrEnum):
    """Standardized message processing status labels for telemetry metrics."""

    INDEXED = "indexed"
    UPDATED = "updated"
    DELETED = "deleted"
    SKIPPED = "skipped"
    NOT_FOUND = "not_found"
    ERROR = "error"

    # Semantic Metadata Processing Statuses
    METADATA_MISSING_CHUNKS = "metadata_missing_chunks"
    METADATA_NOOP = "metadata_noop"
    METADATA_REEMBEDDED = "metadata_reembedded"
    METADATA_PATCHED = "metadata_patched"



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
