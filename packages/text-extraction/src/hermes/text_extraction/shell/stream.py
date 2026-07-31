import io
import logging
from collections.abc import Generator
from typing import BinaryIO

from hermes.text_extraction.exceptions import FileTooLargeError, StreamReadError

logger = logging.getLogger(__name__)


def read_chunk(raw_stream: BinaryIO, chunk_size: int, *, mime_type: str | None = None) -> bytes:
    try:
        return raw_stream.read(chunk_size)
    except OSError as exc:
        logger.error(
            "Failed to read chunk from ingress stream",
            exc_info=True,
            extra={"mime_type": mime_type},
        )
        raise StreamReadError(mime_type=mime_type) from exc


def read_into_memory(
    raw_stream: BinaryIO,
    max_size_bytes: int,
    initial_bytes: bytes,
    chunk_size: int,
    *,
    mime_type: str | None = None,
) -> io.BytesIO:
    """Reads chunked input streams sequentially into an io.BytesIO buffer.

    Args:
        raw_stream: The ingress input stream.
        max_size_bytes: Bounded RAM memory size.
        initial_bytes: Already peeked header bytes.
        chunk_size: Incremental reading size.
        mime_type: Optional mime type context for errors.

    Returns:
        In-memory seekable BytesIO buffer of the entire file.

    Raises:
        FileTooLargeError: If input exceeds max size.
        StreamReadError: If reading the stream fails.
    """
    logger.info(
        "Reading input stream into memory buffer",
        extra={"max_size_bytes": max_size_bytes, "mime_type": mime_type},
    )
    total_bytes: int = len(initial_bytes)

    buffer: io.BytesIO = io.BytesIO()
    buffer.write(initial_bytes)

    while chunk := read_chunk(raw_stream, chunk_size, mime_type=mime_type):
        total_bytes += len(chunk)

        if total_bytes > max_size_bytes:
            logger.error(
                "Stream stream length exceeded maximum size limit",
                extra={
                    "max_size_bytes": max_size_bytes,
                    "total_bytes": total_bytes,
                    "mime_type": mime_type,
                },
            )
            raise FileTooLargeError(max_size_bytes, mime_type=mime_type)

        buffer.write(chunk)

    buffer.seek(0)
    logger.info(
        "Successfully loaded stream into memory buffer",
        extra={"total_bytes": total_bytes, "mime_type": mime_type},
    )
    return buffer


def create_lazy_generator(
    raw_stream: BinaryIO,
    initial_bytes: bytes,
    max_size_bytes: int,
    chunk_size: int,
    *,
    mime_type: str | None = None,
) -> Generator[bytes]:
    """Yields chunks sequentially while validating accumulated size.

    Args:
        raw_stream: The ingress input stream.
        initial_bytes: Already peeked header bytes.
        max_size_bytes: Bounded stream size threshold.
        chunk_size: Incremental reading size.
        mime_type: Optional mime type context for errors.

    Yields:
        Bytes chunks of the stream.

    Raises:
        FileTooLargeError: If input exceeds max size.
        StreamReadError: If reading the stream fails.
    """
    logger.info(
        "Creating lazy generator for stream",
        extra={"max_size_bytes": max_size_bytes, "mime_type": mime_type},
    )
    total_bytes: int = len(initial_bytes)

    yield initial_bytes

    while chunk := read_chunk(raw_stream, chunk_size, mime_type=mime_type):
        total_bytes += len(chunk)

        if total_bytes > max_size_bytes:
            logger.error(
                "Stream chunk length exceeded maximum size limit",
                extra={
                    "max_size_bytes": max_size_bytes,
                    "total_bytes": total_bytes,
                    "mime_type": mime_type,
                },
            )
            raise FileTooLargeError(max_size_bytes, mime_type=mime_type)
        yield chunk
