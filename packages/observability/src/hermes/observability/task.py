import functools
import inspect
import logging
from collections.abc import Callable
from typing import Any

from structlog.stdlib import BoundLogger

from hermes.observability.context import LogContext


def instrument_task(
    name: str | None = None,
    *,
    bind_args: bool = False,
    start_msg: str | None = None,
    finish_msg: str | None = None,
    level: int = logging.INFO,
    error_level: int = logging.ERROR,
    log_duration: bool = True,
    logger: BoundLogger | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for auto-instrumenting sync and async task functions.
    Wraps task execution in a LogContext block for scope binding, timing, and error handling.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        task_name = name or getattr(fn, "__name__", "task")

        def _build_binds(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, object]:
            binds: dict[str, object] = {}
            if bind_args:
                try:
                    sig = inspect.signature(fn)
                    bound_args = sig.bind(*args, **kwargs)
                    bound_args.apply_defaults()
                    for arg_name, arg_val in bound_args.arguments.items():
                        binds[f"arg_{arg_name}"] = arg_val
                except Exception:
                    pass
            return binds

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                binds = _build_binds(args, kwargs)
                with LogContext(
                    name=task_name,
                    start_msg=start_msg,
                    finish_msg=finish_msg,
                    level=level,
                    error_level=error_level,
                    extra_fields=binds,
                    log_duration=log_duration,
                    logger=logger,
                ):
                    return await fn(*args, **kwargs)

            return async_wrapper

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            binds = _build_binds(args, kwargs)
            with LogContext(
                name=task_name,
                start_msg=start_msg,
                finish_msg=finish_msg,
                level=level,
                error_level=error_level,
                extra_fields=binds,
                log_duration=log_duration,
                logger=logger,
            ):
                return fn(*args, **kwargs)

        return sync_wrapper

    return decorator
