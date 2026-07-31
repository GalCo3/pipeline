import functools
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


def log_extraction(mime_type: str) -> Callable[[Callable[..., str]], Callable[..., str]]:
    """Standardizes logging across local extractors."""

    def decorator(func: Callable[..., str]) -> Callable[..., str]:
        @functools.wraps(func)
        def wrapper(payload: Any, max_length: int, *args: Any, **kwargs: Any) -> str:
            logger.info(
                "Starting document text extraction",
                extra={"mime_type": mime_type, "max_length": max_length},
            )

            result: str = func(payload, max_length, *args, **kwargs)

            logger.info(
                "Successfully completed document text extraction",
                extra={
                    "mime_type": mime_type,
                    "max_length": max_length,
                    "extracted_length": len(result),
                },
            )
            return result

        return wrapper

    return decorator
