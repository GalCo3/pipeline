import logging
import time
from collections.abc import Mapping
from types import TracebackType
from typing import Any, cast

import structlog
from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
    get_contextvars,
    reset_contextvars,
    unbind_contextvars,
)
from structlog.stdlib import BoundLogger

from hermes.observability.utils import resolve_log_method


def bind_context(**kwargs: object) -> Mapping[str, Any]:
    """Binds key-value pairs to the current execution context variables."""
    return bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """Unbinds specified keys from current context variables."""
    unbind_contextvars(*keys)


def get_context() -> dict[str, Any]:
    """Returns current context variables as a dictionary."""
    return get_contextvars()


def clear_context() -> None:
    """Clears all current context variables."""
    clear_contextvars()


class LogContext:
    """
    Standardized context manager for binding structured context variables,
    timing execution blocks, and emitting start/finish/error log notifications.
    """

    def __init__(
        self,
        name: str | None = None,
        *,
        start_msg: str | None = None,
        finish_msg: str | None = None,
        level: int = logging.INFO,
        error_level: int = logging.ERROR,
        extra_fields: Mapping[str, object] | None = None,
        extra_finish_fields: Mapping[str, object] | None = None,
        log_duration: bool = True,
        logger: BoundLogger | None = None,
        **kwargs: object,
    ) -> None:
        self.name = name
        self.start_msg = start_msg
        self.finish_msg = finish_msg
        self.level = level
        self.error_level = error_level
        self.extra_fields = dict(extra_fields) if extra_fields else {}
        self.extra_finish_fields = dict(extra_finish_fields) if extra_finish_fields else {}
        self.log_duration = log_duration
        self.logger = logger if logger is not None else cast(BoundLogger, structlog.get_logger())
        self.binds = kwargs

        self._start_time: float | None = None
        self._tokens: Mapping[str, Any] = {}

    def __enter__(self) -> LogContext:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.stop(exc_type=exc_type, exc_val=exc_val, exc_tb=exc_tb)

    def start(self) -> None:
        """Starts the context block timing, binds context variables, and emits start_msg if set."""
        self._start_time = time.perf_counter()

        all_binds: dict[str, object] = {}
        if self.name is not None:
            all_binds["scope"] = self.name
        all_binds.update(self.extra_fields)
        all_binds.update(self.binds)

        if all_binds:
            self._tokens = bind_contextvars(**all_binds)

        if self.start_msg is not None:
            log_fn = resolve_log_method(self.logger, self.level)
            log_fn(self.start_msg)

    def stop(
        self,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        exc_tb: TracebackType | None = None,
    ) -> None:
        """Stops timing, emits finish/error log notification, and resets context variables."""
        try:
            duration_sec = (
                round(time.perf_counter() - self._start_time, 4)
                if self._start_time is not None
                else 0.0
            )

            finish_kwargs: dict[str, object] = dict(self.extra_finish_fields)
            if self.log_duration:
                finish_kwargs["duration_sec"] = duration_sec

            if exc_type is not None:
                # Handle block exception
                error_fn = resolve_log_method(self.logger, self.error_level)
                err_msg = (
                    self.finish_msg
                    if self.finish_msg is not None
                    else (f"{self.name} failed" if self.name else "Operation failed")
                )
                finish_kwargs.update(
                    {
                        "status": "error",
                        "error": str(exc_val),
                        "exception_type": exc_type.__name__,
                    }
                )
                error_fn(err_msg, exc_info=(exc_type, exc_val, exc_tb), **finish_kwargs)
            else:
                finish_msg = (
                    self.finish_msg
                    if self.finish_msg is not None
                    else (f"{self.name} completed" if self.name else None)
                )
                if finish_msg is not None:
                    log_fn = resolve_log_method(self.logger, self.level)
                    log_fn(finish_msg, **finish_kwargs)
        finally:
            if self._tokens:
                reset_contextvars(**self._tokens)
