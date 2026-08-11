import logging
from collections.abc import Callable
from typing import Any, cast

from structlog.stdlib import BoundLogger

LEVEL_MAP: dict[int, str] = {
    logging.DEBUG: "debug",
    logging.INFO: "info",
    logging.WARNING: "warning",
    logging.WARN: "warning",
    logging.ERROR: "error",
    logging.CRITICAL: "critical",
    logging.FATAL: "critical",
}


def resolve_log_method(logger: BoundLogger, level: int) -> Callable[..., Any]:
    """Resolves standard logging integer level to the corresponding structlog bound
    logger method."""
    method_name = LEVEL_MAP.get(level, "info")
    return cast(Callable[..., Any], getattr(logger, method_name, logger.info))
