import json
import logging
from collections.abc import Generator
from typing import Any

import pytest

from hermes.observability import configure_logging, get_logger


@pytest.fixture(autouse=True)
def reset_logging() -> Generator[None]:
    """Fixture to reset standard logging and structlog configurations after each test."""
    yield
    # Reset root logger handlers
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    # Reset logger level
    root.setLevel(logging.WARNING)
    # Reset other loggers
    for logger_name in ["uvicorn", "urllib3"]:
        logging.getLogger(logger_name).setLevel(logging.NOTSET)


def test_production_logging_format(capsys: pytest.CaptureFixture[str]) -> None:
    # Configure logging for production mode
    configure_logging(is_production=True, log_level=logging.INFO)

    logger = get_logger("prod-test")
    logger.info("Hello production world", key="value")

    captured = capsys.readouterr()
    log_output = captured.out.strip()

    # Assert JSON format
    data: dict[str, Any] = json.loads(log_output)
    assert data["message"] == "Hello production world"
    assert data["level"] == "INFO"
    assert data["logger"] == "prod-test"
    # 'key' is not whitelisted, so it must be nested under 'metadata'
    assert data["metadata"]["key"] == "value"
    assert "timestamp" in data
    # Verify ISO 8601 timestamp structure
    assert "T" in data["timestamp"]
    # Verify callsite info nested under source
    assert "source" in data
    assert "file" in data["source"]
    assert "line" in data["source"]
    assert "func" in data["source"]


def test_development_logging_format(capsys: pytest.CaptureFixture[str]) -> None:
    # Configure logging for development mode
    configure_logging(is_production=False, log_level=logging.INFO)

    logger = get_logger("dev-test")
    logger.info("Hello dev world", key="value")

    captured = capsys.readouterr()
    log_output = captured.out.strip()

    # Assert non-JSON format
    assert "Hello dev world" in log_output
    assert "dev-test" in log_output
    assert "key" in log_output and "value" in log_output


def test_standard_library_log_routing(capsys: pytest.CaptureFixture[str]) -> None:
    # Configure logging for production mode
    configure_logging(is_production=True, log_level=logging.INFO)

    # Emit log using Python standard library logger
    std_logger = logging.getLogger("stdlib-test")
    std_logger.info("Hello from stdlib")

    captured = capsys.readouterr()
    log_output = captured.out.strip()

    # Assert standard library log is formatted as JSON
    data: dict[str, Any] = json.loads(log_output)
    assert data["message"] == "Hello from stdlib"
    assert data["level"] == "INFO"
    assert data["logger"] == "stdlib-test"
    assert "timestamp" in data
    # Verify callsite info nested under source
    assert "source" in data
    assert "file" in data["source"]


def test_third_party_silencing() -> None:
    # Setup test logger with dummy initial level
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(logging.DEBUG)

    # Configure logging for production mode
    configure_logging(is_production=True, log_level=logging.INFO)

    # Verify third-party logger was silenced to WARNING
    assert uvicorn_logger.level == logging.WARNING


def test_dynamic_log_level_change(capsys: pytest.CaptureFixture[str]) -> None:
    # Configure logging for production mode starting at INFO
    configure_logging(is_production=True, log_level=logging.INFO)

    logger = get_logger("level-test")

    # Debug logs should be ignored at INFO level
    logger.debug("Should not see this")
    captured = capsys.readouterr()
    assert captured.out.strip() == ""

    # Change level to DEBUG dynamically
    logging.getLogger().setLevel(logging.DEBUG)

    # Debug logs should now be visible
    logger.debug("Should see this now")
    captured = capsys.readouterr()
    log_output = captured.out.strip()

    data: dict[str, Any] = json.loads(log_output)
    assert data["message"] == "Should see this now"
    assert data["level"] == "DEBUG"


def test_mapping_explosion_guard(capsys: pytest.CaptureFixture[str]) -> None:
    # Configure logging for production mode
    configure_logging(is_production=True, log_level=logging.INFO)

    logger = get_logger("guard-test")

    # Emit log with both whitelisted and custom non-whitelisted keys
    logger.info(
        "User action occurred",
        correlation_id="corr-123",
        user_id="usr-999",
        custom_tag="active",
        metadata={"existing_meta": True},
    )

    captured = capsys.readouterr()
    log_output = captured.out.strip()
    data: dict[str, Any] = json.loads(log_output)

    # Whitelisted keys must remain at root level
    assert data["message"] == "User action occurred"
    assert data["correlation_id"] == "corr-123"
    assert "timestamp" in data
    assert "level" in data
    assert "logger" in data

    # Non-whitelisted keys must be nested inside 'metadata'
    assert "user_id" not in data
    assert "custom_tag" not in data
    assert data["metadata"]["user_id"] == "usr-999"
    assert data["metadata"]["custom_tag"] == "active"

    # Pre-existing dict 'metadata' must be merged/preserved
    assert data["metadata"]["existing_meta"] is True


def test_mapping_explosion_guard_non_dict_metadata(capsys: pytest.CaptureFixture[str]) -> None:
    # Configure logging for production mode
    configure_logging(is_production=True, log_level=logging.INFO)

    logger = get_logger("guard-test-non-dict")

    # Emit log with a non-dict metadata argument passed
    logger.info("Test metadata wrapping", extra_key="wrap-me", metadata="string-metadata")

    captured = capsys.readouterr()
    log_output = captured.out.strip()
    data: dict[str, Any] = json.loads(log_output)

    # Extra key must be under metadata
    assert data["metadata"]["extra_key"] == "wrap-me"
    # Pre-existing non-dict metadata must be nested under original_metadata
    assert data["metadata"]["original_metadata"] == "string-metadata"


def test_pii_redaction(capsys: pytest.CaptureFixture[str]) -> None:
    # Configure logging for production mode
    configure_logging(is_production=True, log_level=logging.INFO)

    logger = get_logger("pii-test")

    # Emit log with sensitive keys, credit cards, and SSNs
    logger.info(
        "User logged in",
        password="superpassword123",
        secret_token="token-value",
        credit_card="4111-1111-1111-1111",
        ssn="123-45-6789",
        safe_field="unaffected-value",
        nested_dict={
            "api_key": "sensitive-key-val",
            "nested_safe": "nested-safe-val",
            "nested_list": ["clean", "4111 1111 1111 1111"],
        },
    )

    captured = capsys.readouterr()
    log_output = captured.out.strip()
    data: dict[str, Any] = json.loads(log_output)

    # Verify sensitive keys at root (nested under metadata due to guard) are redacted
    assert data["metadata"]["password"] == "[REDACTED]"
    assert data["metadata"]["secret_token"] == "[REDACTED]"

    # Verify value pattern matching (credit card and SSN) are redacted
    assert data["metadata"]["credit_card"] == "[REDACTED]"
    assert data["metadata"]["ssn"] == "[REDACTED]"

    # Verify safe fields remain untouched
    assert data["metadata"]["safe_field"] == "unaffected-value"

    # Verify nested dict redaction
    nested = data["metadata"]["nested_dict"]
    assert nested["api_key"] == "[REDACTED]"
    assert nested["nested_safe"] == "nested-safe-val"

    # Verify nested list redaction (including credit card match in list)
    assert nested["nested_list"][0] == "clean"
    assert nested["nested_list"][1] == "[REDACTED]"
