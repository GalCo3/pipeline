import logging
import sys
from typing import cast

import structlog
from structlog.stdlib import BoundLogger
from structlog.types import Processor

from hermes.observability.constants import NOISY_LOGGERS
from hermes.observability.logging.processors import (
    add_otel_trace_ids,
    add_source_info,
    mapping_explosion_guard,
    pii_redactor,
    rename_event_and_uppercase_level,
)
from hermes.observability.utils import is_production_environment


def _silence_third_party_loggers(is_production: bool) -> None:
    """Silences noisy third-party loggers in production environments."""
    if not is_production:
        return

    for logger_name in NOISY_LOGGERS:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
        if "access" in logger_name:
            logger.disabled = True
            logger.handlers = [logging.NullHandler()]
            logger.propagate = False


def _get_shared_processors() -> list[Processor]:
    """Returns the base pipeline of processors shared between structlog and standard logging."""
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        add_source_info,
        add_otel_trace_ids,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        rename_event_and_uppercase_level,
        pii_redactor,
        mapping_explosion_guard,
    ]


def _configure_structlog_library(shared_processors: list[Processor]) -> None:
    """Configures global structlog settings with standard formatting wrapper."""
    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def _create_root_logger_handler(
    shared_processors: list[Processor], is_production: bool
) -> logging.Handler:
    """Creates a logging Handler formatted using ProcessorFormatter and adaptive renderer."""
    renderer = (
        structlog.processors.JSONRenderer(ensure_ascii=False)
        if is_production
        else structlog.dev.ConsoleRenderer()
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    return handler


def _setup_root_logger(handler: logging.Handler, level: int) -> None:
    """Configures the root logger with the specified handler and logging level."""
    root_logger = logging.getLogger()
    for existing_handler in root_logger.handlers[:]:
        root_logger.removeHandler(existing_handler)
    root_logger.addHandler(handler)
    root_logger.setLevel(level)


def configure_logging(is_production: bool | None = None, log_level: int = logging.INFO) -> None:
    """
    Configures the global logging engine.
    Applies production JSON or dev console rendering, standardizes timestamps,
    routes standard library logging to structlog, and silences library noise.
    """
    is_prod = is_production if is_production is not None else is_production_environment()

    _silence_third_party_loggers(is_prod)

    shared_processors = _get_shared_processors()
    _configure_structlog_library(shared_processors)

    handler = _create_root_logger_handler(shared_processors, is_prod)
    _setup_root_logger(handler, log_level)


def get_logger(name: str | None = None) -> BoundLogger:
    """
    Returns a configured structlog BoundLogger proxy.
    """
    return cast(BoundLogger, structlog.get_logger(name))
