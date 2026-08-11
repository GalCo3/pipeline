import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from structlog.contextvars import clear_contextvars
from structlog.stdlib import BoundLogger

from hermes.observability.constants import DEFAULT_ENCODING
from hermes.observability.context import LogContext
from hermes.observability.utils import resolve_correlation_id


def _extract_msg_attr(msg: Any, attr: str) -> Any:
    """
    Safely extracts an attribute from a generic Kafka message object.

    Using Any and getattr duck-typing allows this package to work with all
    major Python Kafka libraries (confluent-kafka, aiokafka, kafka-python)
    without introducing a direct dependency on any of them.
    """
    val = getattr(msg, attr, None)
    if callable(val):
        try:
            return val()
        except Exception:
            return None
    return val


def _extract_kafka_headers(
    headers: Sequence[tuple[str | bytes, Any]] | Mapping[str | bytes, Any] | None,
) -> dict[str, str]:
    """
    Extracts and normalizes Kafka headers to lowercase string keys and string values.

    Supports list or dict structures inside header values by serializing them to JSON.
    """
    if not headers:
        return {}
    res: dict[str, str] = {}
    items = headers.items() if isinstance(headers, Mapping) else headers

    for k, v in items:
        key_str = k.decode(DEFAULT_ENCODING, errors="replace") if isinstance(k, bytes) else str(k)

        if isinstance(v, bytes):
            val_str = v.decode(DEFAULT_ENCODING, errors="replace")
        elif isinstance(v, (list, dict)):
            val_str = json.dumps(v)
        else:
            val_str = str(v)

        res[key_str.lower()] = val_str
    return res


class kafka_context(LogContext):
    """
    Context manager for Kafka record processing.
    Extracts Kafka headers, clears contextvars, and binds message metadata.
    """

    def __init__(
        self,
        msg: Any,
        *,
        name: str | None = None,
        start_msg: str | None = None,
        finish_msg: str | None = None,
        level: int = logging.INFO,
        error_level: int = logging.ERROR,
        log_duration: bool = True,
        logger: BoundLogger | None = None,
        **kwargs: object,
    ) -> None:
        bind_dict: dict[str, object] = {
            "correlation_id": resolve_correlation_id(
                _extract_kafka_headers(_extract_msg_attr(msg, "headers"))
            ),
        }
        if (topic := _extract_msg_attr(msg, "topic")) is not None:
            bind_dict["kafka_topic"] = str(topic)
        if (partition := _extract_msg_attr(msg, "partition")) is not None:
            bind_dict["kafka_partition"] = partition
        if (offset := _extract_msg_attr(msg, "offset")) is not None:
            bind_dict["kafka_offset"] = offset
        if (key := _extract_msg_attr(msg, "key")) is not None:
            bind_dict["kafka_key"] = (
                key.decode(DEFAULT_ENCODING, errors="replace")
                if isinstance(key, bytes)
                else str(key)
            )

        bind_dict.update(kwargs)

        super().__init__(
            name=name or (f"kafka_process_{topic}" if topic else "kafka_process"),
            start_msg=start_msg,
            finish_msg=finish_msg,
            level=level,
            error_level=error_level,
            extra_fields=bind_dict,
            log_duration=log_duration,
            logger=logger,
        )

    def __enter__(self) -> kafka_context:
        clear_contextvars()
        super().__enter__()
        return self
