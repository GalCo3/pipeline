import contextlib
import io
import logging
from collections.abc import Generator
from typing import Any, BinaryIO

from hermes.text_extraction.config.settings import AppSettings
from hermes.text_extraction.constants import HEADER_READ_SIZE_BYTES
from hermes.text_extraction.core import detector
from hermes.text_extraction.core.spec import ExtractorSpec, PayloadMode
from hermes.text_extraction.exceptions import (
    ExtractionFailedError,
    HermesExtractionError,
)
from hermes.text_extraction.results import ExtractionResult
from hermes.text_extraction.shell import stream
from hermes.text_extraction.wiring import get_extractor_spec

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _extraction_boundary(settings: AppSettings) -> Generator[dict[str, str | None]]:
    logger.info(
        "Initiating text extraction process",
        extra={
            "max_file_size_bytes": settings.max_file_size_bytes,
            "max_text_length": settings.max_text_length,
        },
    )
    tracker: dict[str, str | None] = {"mime_type": None}
    try:
        yield tracker
        logger.info(
            "Successfully completed text extraction",
            extra={"mime_type": tracker["mime_type"]},
        )
    except HermesExtractionError as exc:
        logger.error(
            "Text extraction halted by expected extraction exception",
            extra={
                "exception_class": type(exc).__name__,
                "mime_type": tracker["mime_type"] or exc.mime_type,
                "details": str(exc),
            },
        )
        raise
    except Exception as exc:
        logger.exception(
            "Text extraction failed due to an unexpected system error",
            extra={"mime_type": tracker["mime_type"]},
        )
        raise ExtractionFailedError(mime_type=tracker["mime_type"]) from exc


def extract_text(
    input_stream: BinaryIO,
    settings: AppSettings,
) -> ExtractionResult:
    """Central workflow synchronization engine using Smart Ingress Routing.

    Args:
        input_stream: The raw input stream (possibly unrewindable).
        settings: Bounded configuration values.

    Returns:
        The extracted document text along with its detected MIME type.

    Raises:
        FileTooLargeError: If stream exceeds max file size.
        UnsupportedFormatError: If format is not supported.
        CorruptDocumentError: If parser encounters structural faults.
        NetworkExtractionError: If network extraction fails.
        TextLimitExceededError: If the extracted text length exceeds the limit.
        ExtractionFailedError: For generic/unexpected internal errors.
        HermesExtractionError: Base domain exception for all expected extraction errors.
    """
    with _extraction_boundary(settings) as tracker:
        # Delegate stream access entirely to Imperative Shell
        header_bytes: bytes = stream.read_chunk(input_stream, HEADER_READ_SIZE_BYTES)

        mime_type = detector.get_mime_type(io.BytesIO(header_bytes))
        tracker["mime_type"] = mime_type
        logger.info(
            "Detected file MIME type",
            extra={"mime_type": mime_type},
        )
        spec: ExtractorSpec = get_extractor_spec(mime_type)

        payload: io.BytesIO | Generator[bytes] | None = None
        try:
            # Smart Ingress Routing
            stream_params: dict[str, Any] = {
                "raw_stream": input_stream,
                "initial_bytes": header_bytes,
                "max_size_bytes": settings.max_file_size_bytes,
                "chunk_size": settings.chunk_size_bytes,
                "mime_type": mime_type,
            }
            if spec.payload_mode is PayloadMode.BUFFER:
                payload = stream.read_into_memory(**stream_params)
            else:
                payload = stream.create_lazy_generator(**stream_params)

            # Call the actual extractor function based on the spec
            fn_params: dict[str, Any] = {
                "payload": payload,
                "max_length": settings.max_text_length,
            }
            if spec.needs_tika_url:
                fn_params.update(
                    {
                        "tika_url": str(settings.tika_server_url),
                        "timeout_seconds": settings.network_timeout_seconds,
                        "chunk_size": settings.chunk_size_bytes,
                        "mime_type": mime_type,
                    }
                )

            return ExtractionResult(text=spec.fn(**fn_params), mime_type=mime_type)
        finally:
            # Explicitly close the payload to free memory (though Python should
            # eventually recycle it anyway)
            if payload is not None and (
                isinstance(payload, io.BytesIO) or hasattr(payload, "close")
            ):
                payload.close()
