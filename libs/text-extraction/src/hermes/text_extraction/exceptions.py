class HermesExtractionError(Exception):
    """Base exception for all domain-specific errors in the hermes.text-extraction package."""

    def __init__(self, message: str, *, mime_type: str | None = None) -> None:
        self.mime_type = mime_type
        super().__init__(message)


class FileTooLargeError(HermesExtractionError):
    """Raised when an incoming stream exceeds the defined RAM boundary."""

    def __init__(self, max_size_bytes: int, *, mime_type: str | None = None) -> None:
        self.max_size_bytes = max_size_bytes
        super().__init__(
            f"Stream exceeds maximum allowed size of {max_size_bytes} bytes.",
            mime_type=mime_type,
        )


class UnsupportedFormatError(HermesExtractionError):
    """Raised when the router cannot find an extraction contract for the detected MIME type."""

    def __init__(self, mime_type: str) -> None:
        self.detected_mime_type = mime_type
        super().__init__(f"Unsupported document format: '{mime_type}'", mime_type=mime_type)


class CorruptDocumentError(HermesExtractionError):
    """Raised when a document archive or structure cannot be parsed."""

    def __init__(self, mime_type: str) -> None:
        super().__init__(
            f"Invalid or corrupt document of MIME type: {mime_type}",
            mime_type=mime_type,
        )


class NetworkExtractionError(HermesExtractionError):
    """Raised when remote extraction via Apache Tika fails."""

    def __init__(
        self,
        message: str = "Remote text extraction failed.",
        *,
        mime_type: str | None = None,
    ) -> None:
        super().__init__(message, mime_type=mime_type)


class StreamReadError(HermesExtractionError):
    """Raised when the ingress stream cannot be read."""

    def __init__(self, *, mime_type: str | None = None) -> None:
        super().__init__("Failed to read input stream.", mime_type=mime_type)


class ExtractionFailedError(HermesExtractionError):
    """Raised when extraction fails for an unexpected internal reason."""

    def __init__(self, *, mime_type: str | None = None) -> None:
        super().__init__("Text extraction failed.", mime_type=mime_type)


class TextLimitExceededError(HermesExtractionError):
    """Raised when the extracted text exceeds the maximum character limit."""

    def __init__(self, max_length: int, *, mime_type: str | None = None) -> None:
        self.max_length = max_length
        super().__init__(
            f"Extracted text exceeds the maximum allowed length of {max_length} characters.",
            mime_type=mime_type,
        )
