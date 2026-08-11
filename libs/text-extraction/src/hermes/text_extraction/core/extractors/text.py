import codecs
import logging
from codecs import BufferedIncrementalDecoder
from collections.abc import Generator, Iterable

from hermes.text_extraction.constants import MimeType
from hermes.text_extraction.core.decorators import log_extraction
from hermes.text_extraction.core.utils import join_chunks_with_limit

logger = logging.getLogger(__name__)


def _iter_text(payload: Iterable[bytes]) -> Generator[str]:
    """Generates decoded text chunks from a byte stream."""
    # Incremental decoder safely handles UTF-8 bytes split across chunks
    decoder: BufferedIncrementalDecoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    for chunk in payload:
        text_chunk: str = decoder.decode(chunk)
        if text_chunk:
            yield text_chunk

    # Flush any remaining state in the decoder
    final_chunk: str = decoder.decode(b"", final=True)
    if final_chunk:
        yield final_chunk


@log_extraction(MimeType.TEXT)
def extract(payload: Iterable[bytes], max_length: int) -> str:
    """Pure stream decoder for standard text / markdown.

    Args:
        payload: Iterable stream yielding chunks of bytes.
        max_length: Maximum characters to yield.

    Returns:
        The decoded text.
    """
    return join_chunks_with_limit(
        _iter_text(payload),
        max_length,
        mime_type=MimeType.TEXT,
        joiner="",
    )
