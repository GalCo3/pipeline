import uuid
from collections.abc import Mapping
from typing import Any


def resolve_correlation_id(
    headers: Mapping[str, Any] | None,
    keys: tuple[str, ...] = ("correlation_id", "x-correlation-id", "x-request-id"),
) -> str:
    """
    Resolves correlation_id from a mapping of headers or returns a generated UUID.
    Performs case-insensitive key lookup.
    """
    if not headers:
        return str(uuid.uuid4())

    for key in keys:
        key_lower = key.lower()
        for hk, hv in headers.items():
            if hk.lower() == key_lower and hv:
                return str(hv)

    return str(uuid.uuid4())
