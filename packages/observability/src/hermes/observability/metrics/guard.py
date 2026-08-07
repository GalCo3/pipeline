import logging
import re
from typing import Any

from opentelemetry import trace

from hermes.observability.constants import HIGH_CARDINALITY_KEYS

logger = logging.getLogger(__name__)

UUID_REGEX = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
NUMERIC_ID_REGEX = re.compile(r"^\d{5,}$")


def _is_high_cardinality(key: str, val_str: str) -> bool:
    """Detects if a key or value represents a high-cardinality identifier."""
    return (
        key.lower() in HIGH_CARDINALITY_KEYS
        or bool(UUID_REGEX.match(val_str))
        or bool(EMAIL_REGEX.match(val_str))
        or bool(NUMERIC_ID_REGEX.match(val_str))
    )


def clean_labels(
    metric_name: str,
    labels: dict[str, Any] | None,
    allowed_labels: list[str] | None = None,
) -> dict[str, str]:
    """
    Cleans metric labels by dropping non-whitelisted labels and redacting
    high-cardinality values to generic_id, routing original data to the active Trace
    Span attributes.
    """
    if not labels:
        return {}

    cleaned: dict[str, str] = {}
    span = trace.get_current_span()
    span_valid = span is not None and span.get_span_context().is_valid

    for key, val in labels.items():
        val_str = str(val)

        # 1. Enforce allowed labels whitelist (if configured)
        if allowed_labels is not None and key not in allowed_labels:
            logger.debug(
                "Label '%s' is not in the whitelist for metric '%s'. Dropping label.",
                key,
                metric_name,
            )
            if span_valid:
                span.set_attribute(f"metric.dropped.{metric_name}.{key}", val_str)
            continue

        # 2. Check for high cardinality identifiers
        if _is_high_cardinality(key, val_str):
            logger.debug(
                "High cardinality detected on label '%s' in metric '%s'. "
                "Redacting value to generic_id.",
                key,
                metric_name,
            )
            if span_valid:
                span.set_attribute(f"metric.redacted.{metric_name}.{key}", val_str)
            cleaned[key] = "generic_id"
        else:
            cleaned[key] = val_str

    return cleaned
