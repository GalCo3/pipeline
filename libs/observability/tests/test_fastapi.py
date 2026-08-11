import json
import logging
from collections.abc import Generator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from structlog.contextvars import clear_contextvars

from hermes.observability import add_fastapi_observability, configure_logging, get_logger


@pytest.fixture(autouse=True)
def _reset_logging() -> Generator[None]:
    clear_contextvars()
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
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
    logs = [json.loads(line) for line in lines]
    return [log for log in logs if log.get("logger") not in ("httpx", "httpcore")]


def test_fastapi_correlation_id_and_response_headers(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(is_production=True)

    app = FastAPI()
    add_fastapi_observability(app)

    @app.get("/items/{item_id}")
    def read_item(item_id: int) -> dict[str, str]:
        logger = get_logger("item_handler")
        logger.info("Handling item read")
        return {"item_id": str(item_id)}

    client = TestClient(app)
    response = client.get("/items/42")

    assert response.status_code == 200
    assert response.json() == {"item_id": "42"}
    assert "X-Correlation-ID" in response.headers
    correlation_id = response.headers["X-Correlation-ID"]
    assert len(correlation_id) > 0

    logs = _parse_logs(capsys.readouterr().out)
    assert len(logs) == 2

    # Handler log assertion
    assert logs[0]["message"] == "Handling item read"
    assert _get_field(logs[0], "correlation_id") == correlation_id
    assert _get_field(logs[0], "http_method") == "GET"

    # Access log assertion
    assert "HTTP GET /items/42 - 200" in logs[1]["message"]
    assert _get_field(logs[1], "status_code") == 200
    assert _get_field(logs[1], "duration_sec") is not None


def test_fastapi_custom_correlation_id_and_header_capture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(is_production=True)

    app = FastAPI()
    add_fastapi_observability(app, capture_headers=["User-Agent"])

    @app.get("/user")
    def get_user() -> dict[str, str]:
        return {"user": "alice"}

    client = TestClient(app)
    custom_cid = "custom-correlation-12345"
    response = client.get(
        "/user",
        headers={"X-Correlation-ID": custom_cid, "User-Agent": "PytestClient/1.0"},
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == custom_cid

    logs = _parse_logs(capsys.readouterr().out)
    assert len(logs) == 1
    log_data = logs[0]

    assert _get_field(log_data, "correlation_id") == custom_cid
    assert _get_field(log_data, "header_user_agent") == "PytestClient/1.0"


def test_fastapi_excluded_paths(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(is_production=True)

    app = FastAPI()
    add_fastapi_observability(app, excluded_paths=["/health"])

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    logs = _parse_logs(capsys.readouterr().out)
    assert len(logs) == 0


def test_fastapi_unhandled_exception_logging(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(is_production=True)

    app = FastAPI()
    add_fastapi_observability(app)

    @app.get("/crash")
    def crash() -> None:
        raise RuntimeError("Something exploded")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/crash")

    assert response.status_code == 500

    logs = _parse_logs(capsys.readouterr().out)
    assert len(logs) == 1
    log_data = logs[0]

    assert log_data["level"] == "ERROR"
    assert "HTTP GET /crash - 500 Internal Server Error" in log_data["message"]
    assert _get_field(log_data, "error") == "Something exploded"


def test_fastapi_default_excluded_paths(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(is_production=True)

    app = FastAPI()
    add_fastapi_observability(app)

    @app.get("/ready")
    def readiness_check() -> dict[str, str]:
        return {"status": "ready"}

    client = TestClient(app)
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}

    logs = _parse_logs(capsys.readouterr().out)
    assert len(logs) == 0
