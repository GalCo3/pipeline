import logging
from collections.abc import Iterable

from hermes.text_extraction.exceptions import TextLimitExceededError

logger = logging.getLogger(__name__)


def join_chunks_with_limit(
    chunks: Iterable[str],
    max_length: int,
    mime_type: str,
    joiner: str = "",
) -> str:
    """Consumes chunks, enforcing a maximum string length, and returns the joined result.

    Args:
        chunks: An iterable of text chunks.
        max_length: The maximum permitted length of the combined string.
        mime_type: The MIME type of the document.
        joiner: The string used to join the chunks.

    Returns:
        The combined text string.

    Raises:
        TextLimitExceededError: If the maximum length is exceeded during iteration or post-join.
    """
    extracted_chunks: list[str] = []
    current_length: int = 0

    for chunk in chunks:
        if not chunk:
            continue

        if extracted_chunks and joiner:
            current_length += len(joiner)

        extracted_chunks.append(chunk)
        current_length += len(chunk)

        if current_length > max_length:
            logger.error(
                "Extraction limit exceeded during loop.",
                extra={
                    "mime_type": mime_type,
                    "max_length": max_length,
                    "current_length": current_length,
                },
            )
            raise TextLimitExceededError(max_length, mime_type=mime_type)

    result: str = joiner.join(extracted_chunks)
    if len(result) > max_length:
        logger.error(
            "Extraction limit exceeded after join",
            extra={
                "mime_type": mime_type,
                "max_length": max_length,
                "current_length": len(result),
            },
        )
        raise TextLimitExceededError(max_length, mime_type=mime_type)
    return result
