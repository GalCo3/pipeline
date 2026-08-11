import json
import logging
from collections.abc import Generator
from typing import Any

import pytest
from structlog.contextvars import clear_contextvars

from hermes.observability import (
    bind_context,
    clear_context,
    configure_logging,
    get_context,
    get_logger,
    instrument_task,
    unbind_context,
)


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


def test_context_helpers() -> None:
    clear_context()
    assert get_context() == {}

    bind_context(tenant_id="acme", env="prod")
    assert get_context() == {"tenant_id": "acme", "env": "prod"}

    unbind_context("tenant_id")
    assert get_context() == {"env": "prod"}

    clear_context()
    assert get_context() == {}


def test_instrument_task_sync(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(is_production=True)
    logger = get_logger("task_test")

    @instrument_task(name="sync_cron_job", bind_args=True)
    def process_data(batch_id: int, mode: str = "fast") -> str:
        logger.info("Doing batch processing")
        return "success"

    res = process_data(101, mode="full")
    assert res == "success"

    logs = _parse_logs(capsys.readouterr().out)
    assert len(logs) == 2

    # Inside task log
    assert logs[0]["message"] == "Doing batch processing"
    assert _get_field(logs[0], "arg_batch_id") == 101
    assert _get_field(logs[0], "arg_mode") == "full"
    assert _get_field(logs[0], "scope") == "sync_cron_job"

    # Finish completion log
    assert logs[1]["message"] == "sync_cron_job completed"
    assert _get_field(logs[1], "duration_sec") is not None


@pytest.mark.asyncio
async def test_instrument_task_async(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(is_production=True)
    logger = get_logger("async_task_test")

    @instrument_task()
    async def async_job(job_id: str) -> str:
        logger.info("Executing async task")
        return "done"

    res = await async_job("job_77")
    assert res == "done"

    logs = _parse_logs(capsys.readouterr().out)
    assert len(logs) == 2

    assert logs[0]["message"] == "Executing async task"
    assert _get_field(logs[0], "scope") == "async_job"
    assert logs[1]["message"] == "async_job completed"


def test_instrument_task_exception(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(is_production=True)

    @instrument_task(name="failing_task")
    def fail() -> None:
        raise ValueError("Task error")

    with pytest.raises(ValueError, match="Task error"):
        fail()

    logs = _parse_logs(capsys.readouterr().out)
    assert len(logs) == 1
    log = logs[0]

    assert log["level"] == "ERROR"
    assert log["message"] == "failing_task failed"
    assert _get_field(log, "error") == "Task error"
    assert _get_field(log, "exception_type") == "ValueError"
