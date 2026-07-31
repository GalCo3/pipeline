from __future__ import annotations

import logging
import typing
from collections.abc import Iterable

import requests
from requests import Response, Session

from hermes.text_extraction.constants import IMAGE_MIME_TYPES, MimeType
from hermes.text_extraction.core.utils import join_chunks_with_limit
from hermes.text_extraction.exceptions import NetworkExtractionError

logger = logging.getLogger(__name__)


def _prepare_request(tika_url: str, mime_type: str | None) -> tuple[str, dict[str, str]]:
    """Pure helper to format endpoint URL and prepare Accept / Content-Type headers."""
    endpoint: str = f"{tika_url.rstrip('/')}/tika"
    headers: dict[str, str] = {"Accept": "text/plain"}

    if mime_type:
        headers["Content-Type"] = mime_type
        if mime_type in IMAGE_MIME_TYPES:
            headers["X-Tika-OCRLanguage"] = "heb+eng"

    return endpoint, headers


def _execute_network_request(
    session: Session,
    url: str,
    payload: Iterable[bytes],
    headers: dict[str, str],
    timeout_seconds: float,
    mime_type: str | None,
) -> Response:
    """Impure helper to dispatch PUT request to Apache Tika and raise mapped exceptions."""
    try:
        response: Response = session.put(
            url,
            data=payload,
            headers=headers,
            timeout=timeout_seconds,
            stream=True,
        )
        response.raise_for_status()
        return response
    except requests.exceptions.Timeout as error:
        logger.error(
            "Remote text extraction timed out",
            extra={"mime_type": mime_type, "timeout_seconds": timeout_seconds},
        )
        raise NetworkExtractionError(
            "Remote text extraction timed out",
            mime_type=mime_type,
        ) from error
    except requests.exceptions.HTTPError as error:
        status_code: int | None = error.response.status_code if error.response is not None else None
        details: str = error.response.text if error.response is not None else "No response body"
        logger.error(
            "Remote text extraction returned error status",
            extra={
                "mime_type": mime_type,
                "status_code": status_code,
                "details": details,
            },
        )
        raise NetworkExtractionError(
            f"Remote text extraction returned an error response (Status: {status_code}). Details: {details}",
            mime_type=mime_type,
        ) from error
    except requests.exceptions.RequestException as error:
        logger.error(
            "Remote text extraction network call failed",
            extra={"mime_type": mime_type, "error": str(error)},
        )
        raise NetworkExtractionError(
            f"Remote text extraction network call failed. Details: {error}",
            mime_type=mime_type,
        ) from error


def extract_via_network(
    payload: Iterable[bytes],
    max_length: int,
    tika_url: str,
    timeout_seconds: float,
    chunk_size: int,
    *,
    mime_type: str | None = None,
    session: Session | None = None,
) -> str:
    """Pipes a stream generator payload directly to Apache Tika via chunked upload.

    Args:
        payload: Byte generator of the document stream.
        max_length: Max text character length to return.
        tika_url: Apache Tika REST server URL.
        timeout_seconds: Network client timeout.
        chunk_size: Chunk size to iterate text response.
        mime_type: Optional Content-Type header.
        session: Injectable requests.Session instance.

    Returns:
        Extracted plain text.

    Raises:
        NetworkExtractionError: If connection or HTTP call fails.
    """
    target_endpoint_url, headers = _prepare_request(tika_url, mime_type)

    logger.info(
        "Sending document payload to Apache Tika server",
        extra={"mime_type": mime_type, "tika_url": target_endpoint_url},
    )

    session_resolved: Session = session or Session()
    try:
        response: Response = _execute_network_request(
            session=session_resolved,
            url=target_endpoint_url,
            payload=payload,
            headers=headers,
            timeout_seconds=timeout_seconds,
            mime_type=mime_type,
        )

        logger.info(
            "Successfully received response from Apache Tika server",
            extra={"mime_type": mime_type},
        )

        chunks: Iterable[str] = typing.cast(
            Iterable[str], response.iter_content(chunk_size=chunk_size, decode_unicode=True)
        )
        return join_chunks_with_limit(
            chunks, max_length, mime_type=mime_type or MimeType.UNKNOWN, joiner=""
        )
    finally:
        if session is None:
            session_resolved.close()
