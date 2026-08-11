import json
import logging
from collections.abc import Generator
from typing import Any

import pytest
from structlog.contextvars import clear_contextvars, get_contextvars

from hermes.observability import LogContext, configure_logging, get_logger


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


def test_log_context_binds(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(is_production=True)
    logger = get_logger("test_binds")

    with LogContext(user_id="usr_123", tenant="acme"):
        logger.info("Processing order")
        assert get_contextvars() == {"user_id": "usr_123", "tenant": "acme"}

    # Verify contextvars are reset upon exiting the with block
    assert get_contextvars() == {}

    captured = capsys.readouterr().out.strip()
    log_data = json.loads(captured)
    assert log_data["message"] == "Processing order"
    assert _get_field(log_data, "user_id") == "usr_123"
    assert _get_field(log_data, "tenant") == "acme"


def test_log_context_start_and_finish_messages(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(is_production=True)

    with LogContext(
        name="payment_flow",
        start_msg="Starting payment",
        finish_msg="Payment completed",
        order_id="ord_999",
    ):
        pass

    captured = capsys.readouterr().out.strip()
    raw_lines = [line for line in captured.split("\n") if line.strip()]
    logs = [json.loads(line) for line in raw_lines]
    assert len(logs) == 2

    # Start message assertion
    assert logs[0]["message"] == "Starting payment"
    assert _get_field(logs[0], "scope") == "payment_flow"
    assert _get_field(logs[0], "order_id") == "ord_999"

    # Finish message assertion
    assert logs[1]["message"] == "Payment completed"
    assert _get_field(logs[1], "scope") == "payment_flow"
    assert _get_field(logs[1], "order_id") == "ord_999"
    assert _get_field(logs[1], "duration_sec") is not None
    assert isinstance(_get_field(logs[1], "duration_sec"), float)


def test_log_context_exception_handling(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(is_production=True)

    with (
        pytest.raises(ValueError, match="Database connection failed"),
        LogContext(name="db_transaction", db_name="primary"),
    ):
        raise ValueError("Database connection failed")

    # Context variables must still be reset after exception
    assert get_contextvars() == {}

    captured = capsys.readouterr().out.strip()
    log_data = json.loads(captured)

    assert log_data["level"] == "ERROR"
    assert log_data["message"] == "db_transaction failed"
    assert _get_field(log_data, "scope") == "db_transaction"
    assert _get_field(log_data, "db_name") == "primary"
    assert _get_field(log_data, "status") == "error"
    assert _get_field(log_data, "error") == "Database connection failed"
    assert _get_field(log_data, "exception_type") == "ValueError"
    assert _get_field(log_data, "duration_sec") is not None


def test_nested_log_contexts(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(is_production=True)
    logger = get_logger("nested_test")

    with LogContext(outer_key="outer_val"):
        logger.info("Inside outer")
        with LogContext(inner_key="inner_val"):
            logger.info("Inside inner")
        logger.info("Back in outer")

    assert get_contextvars() == {}

    captured = capsys.readouterr().out.strip()
    raw_lines = [line for line in captured.split("\n") if line.strip()]
    logs = [json.loads(line) for line in raw_lines]
    assert len(logs) == 3

    assert _get_field(logs[0], "outer_key") == "outer_val"
    assert _get_field(logs[0], "inner_key") is None

    assert _get_field(logs[1], "outer_key") == "outer_val"
    assert _get_field(logs[1], "inner_key") == "inner_val"

    assert _get_field(logs[2], "outer_key") == "outer_val"
    assert _get_field(logs[2], "inner_key") is None
