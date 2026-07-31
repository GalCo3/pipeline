import io

import filetype

from hermes.text_extraction.constants import HEADER_READ_SIZE_BYTES, NULL_BYTE, MimeType


def get_mime_type(buffer: io.BytesIO) -> str:
    """Sniffs magic bytes signatures using magic number check and plain text sniffer.

    Args:
        buffer: The stream buffer containing header bytes.

    Returns:
        The detected MIME type string, or MimeType.UNKNOWN.
    """
    buffer.seek(0)

    try:
        header_bytes: bytes = buffer.read(HEADER_READ_SIZE_BYTES)

        # Try to match binary structures (PDF, ZIP/Office Open XML, PNG)
        kind: filetype.Type | None = filetype.guess(header_bytes)

        if kind is not None:
            return kind.mime

        # Fallback heuristic for plain text files (absence of null bytes)
        if NULL_BYTE not in header_bytes:
            return MimeType.TEXT

        return MimeType.UNKNOWN
    except Exception:
        return MimeType.UNKNOWN
    finally:
        buffer.seek(0)
