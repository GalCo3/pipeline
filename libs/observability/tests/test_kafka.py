import json
import logging
from collections.abc import Generator
from typing import Any

import pytest
from structlog.contextvars import clear_contextvars, get_contextvars

from hermes.observability import (
    configure_logging,
    get_logger,
    kafka_context,
)
from hermes.observability.kafka import _extract_kafka_headers


@pytest.fixture(autouse=True)
def _reset_logging() -> Generator[None]:
    clear_contextvars()
    yield
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    clear_contextvars()


def _get_field(log: dict[str, Any], key: str) -> Any:
    if key in log:
        return log[key]
    metadata = log.get("metadata", {})
    return metadata.get(key)


def _parse_logs(stdout: str) -> list[dict[str, Any]]:
    lines = [line.strip() for line in stdout.strip().split("\n") if line.strip()]
    return [json.loads(line) for line in lines]


class MockAioKafkaRecord:
    def __init__(
        self, topic: str, partition: int, offset: int, key: bytes, headers: list[tuple[str, bytes]]
    ) -> None:
        self.topic = topic
        self.partition = partition
        self.offset = offset
        self.key = key
        self.headers = headers


class MockConfluentKafkaMessage:
    def __init__(
        self, topic: str, partition: int, offset: int, key: str, headers: list[tuple[str, bytes]]
    ) -> None:
        self._topic = topic
        self._partition = partition
        self._offset = offset
        self._key = key
        self._headers = headers

    def topic(self) -> str:
        return self._topic

    def partition(self) -> int:
        return self._partition

    def offset(self) -> int:
        return self._offset

    def key(self) -> str:
        return self._key

    def headers(self) -> list[tuple[str, bytes]]:
        return self._headers


def test_internal_extract_kafka_headers() -> None:
    # 1. Test basic extraction
    headers = [("correlation_id", b"correlation-123"), ("custom_header", "plain-string")]
    extracted = _extract_kafka_headers(headers)
    assert extracted["correlation_id"] == "correlation-123"
    assert extracted["custom_header"] == "plain-string"

    # 2. Test JSON serialization of lists and dictionaries inside header values
    complex_headers = [
        ("user_roles", ["admin", "editor"]),
        ("metadata_dict", {"env": "prod", "version": 1.2}),
    ]
    extracted_complex = _extract_kafka_headers(complex_headers)
    assert extracted_complex["user_roles"] == '["admin", "editor"]'

    # Parse back the serialized JSON dictionary to verify correctness
    parsed_dict = json.loads(extracted_complex["metadata_dict"])
    assert parsed_dict["env"] == "prod"
    assert parsed_dict["version"] == 1.2


def test_kafka_context_property_record(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(is_production=True)
    logger = get_logger("test_kafka")

    record = MockAioKafkaRecord(
        topic="orders.v1",
        partition=1,
        offset=100,
        key=b"order_123",
        headers=[("x-correlation-id", b"cid-kafka-999")],
    )

    with kafka_context(record):
        logger.info("Processing order event")

    assert get_contextvars() == {}

    logs = _parse_logs(capsys.readouterr().out)
    assert len(logs) == 2

    # Inner event log
    assert logs[0]["message"] == "Processing order event"
    assert _get_field(logs[0], "correlation_id") == "cid-kafka-999"
    assert _get_field(logs[0], "kafka_topic") == "orders.v1"
    assert _get_field(logs[0], "kafka_partition") == 1
    assert _get_field(logs[0], "kafka_offset") == 100
    assert _get_field(logs[0], "kafka_key") == "order_123"

    # Completion log
    assert "completed" in logs[1]["message"]
    assert _get_field(logs[1], "scope") == "kafka_process_orders.v1"
    assert _get_field(logs[1], "duration_sec") is not None


def test_kafka_context_method_message(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(is_production=True)
    logger = get_logger("test_kafka")

    msg = MockConfluentKafkaMessage(
        topic="payments.v1",
        partition=0,
        offset=50,
        key="user_789",
        headers=[("x-correlation-id", b"cid-payment-111")],
    )

    with kafka_context(msg, name="custom_payment_scope"):
        logger.info("Processing payment")

    logs = _parse_logs(capsys.readouterr().out)
    assert len(logs) == 2
    assert _get_field(logs[0], "correlation_id") == "cid-payment-111"
    assert _get_field(logs[0], "kafka_topic") == "payments.v1"
    assert _get_field(logs[0], "kafka_key") == "user_789"
    assert _get_field(logs[1], "scope") == "custom_payment_scope"
