import logging
from collections.abc import Generator

import pytest
from structlog.contextvars import clear_contextvars

from hermes.observability import get_logger, init_observability


@pytest.fixture(autouse=True)
def _reset_logging() -> Generator[None]:
    clear_contextvars()
    yield
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    clear_contextvars()


def test_init_observability_basic() -> None:
    res = init_observability(
        service_name="test-service",
        is_production=True,
        log_level=logging.INFO,
        enable_telemetry=False,
    )

    assert res["logging"] is True
    assert res["telemetry"] is False

    logger = get_logger("init_test")
    assert logger is not None
