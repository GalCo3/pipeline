# settings
from __future__ import annotations

from enum import Enum
from typing import Final

ENV_PREFIX: Final[str] = "HERMES_TEXT_EXTRACTION__"
BYTES_IN_MB: Final[int] = 1024 * 1024

HEADER_READ_SIZE_BYTES: Final[int] = 1024 * 8

DEFAULT_MAX_TEXT_LENGTH: Final[int] = 1_000_000
DEFAULT_MAX_FILE_SIZE_MB: Final[int] = 1000
DEFAULT_CHUNK_SIZE_BYTES: Final[int] = 1024 * 8
DEFAULT_NETWORK_TIMEOUT_SECONDS: Final[float] = 30.0

NULL_BYTE: Final[bytes] = b"\x00"


class MimeType(str, Enum):
    """Strict registry of supported MIME types to prevent typo-driven bugs."""

    PDF = "application/pdf"
    PNG = "image/png"
    JPEG = "image/jpeg"
    WEBP = "image/webp"
    TIFF = "image/tiff"
    BMP = "image/bmp"
    ICO = "image/x-icon"
    DOC_LEGACY = "application/msword"
    DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    TEXT = "text/plain"
    UNKNOWN = "application/octet-stream"


IMAGE_MIME_TYPES: Final[frozenset[str]] = frozenset(
    {
        MimeType.PNG,
        MimeType.JPEG,
        MimeType.WEBP,
        MimeType.TIFF,
        MimeType.BMP,
        MimeType.ICO,
    }
)


TIKA_REMOTE_MIME_TYPES: Final[frozenset[str]] = frozenset(
    {
        MimeType.DOC_LEGACY,
        *IMAGE_MIME_TYPES,
    }
)
