import re
from typing import Final

from structlog.types import EventDict, WrappedLogger

from hermes.observability.constants import SENSITIVE_KEY_SUBSTRINGS

CREDIT_CARD_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b(?:\d[- ]?){12,15}\d\b")
SSN_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b")
REDACTED_STR: Final[str] = "[REDACTED]"


def _is_sensitive_key(key: str) -> bool:
    key_lower = key.lower()
    return any(sub in key_lower for sub in SENSITIVE_KEY_SUBSTRINGS)


def _redact_value(val: object) -> object:
    if isinstance(val, str) and (CREDIT_CARD_PATTERN.search(val) or SSN_PATTERN.search(val)):
        return REDACTED_STR
    return val


def redact_item(key: str, val: object) -> object:
    """
    Recursively scans and redacts sensitive PII keys and values.
    """
    if _is_sensitive_key(key):
        return REDACTED_STR
    if isinstance(val, dict):
        return {str(k): redact_item(str(k), v) for k, v in val.items()}
    if isinstance(val, list):
        return [redact_item(key, item) for item in val]
    return _redact_value(val)


def pii_redactor(_logger: WrappedLogger, _method_name: str, event_dict: EventDict) -> EventDict:
    """
    Interceptors for structlog that redacts sensitive PII (passwords, tokens, CC numbers, SSNs)
    from keys and string values in-memory.
    """
    for key, val in list(event_dict.items()):
        if not key.startswith("_"):
            event_dict[key] = redact_item(key, val)

    return event_dict
