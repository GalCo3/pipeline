import pytest
import requests
from tests.mocks import TikaMockConfigurator

from hermes.text_extraction.exceptions import NetworkExtractionError, TextLimitExceededError
from hermes.text_extraction.shell import tika


def test_tika_extract_success(mock_tika: TikaMockConfigurator) -> None:
    # Arrange
    rsps = mock_tika()
    payload = (chunk for chunk in [b"chunk1", b"chunk2"])

    # Act
    result = tika.extract_via_network(
        payload=payload,
        max_length=100,
        tika_url="http://localhost:9998",
        timeout_seconds=5.0,
        chunk_size=1024,
    )

    # Assert
    assert result == "Hello Tika World!"
    assert len(rsps.calls) == 1
    call = rsps.calls[0]
    assert call.request.url == "http://localhost:9998/tika"
    assert call.request.headers.get("Accept") == "text/plain"


def test_tika_extract_limit(mock_tika: TikaMockConfigurator) -> None:
    # Arrange
    mock_tika()
    payload = (chunk for chunk in [b"chunk1"])

    # Act & Assert
    with pytest.raises(TextLimitExceededError):
        tika.extract_via_network(
            payload=payload,
            max_length=5,
            tika_url="http://localhost:9998",
            timeout_seconds=5.0,
            chunk_size=2,
        )


def test_tika_extract_timeout(mock_tika: TikaMockConfigurator) -> None:
    # Arrange
    mock_tika(body=requests.exceptions.Timeout("Connection timed out"))
    payload = (chunk for chunk in [b"chunk1"])

    # Act & Assert
    with pytest.raises(NetworkExtractionError) as exc_info:
        tika.extract_via_network(
            payload=payload,
            max_length=100,
            tika_url="http://localhost:9998",
            timeout_seconds=5.0,
            chunk_size=1024,
        )
    assert "timed out" in str(exc_info.value)


def test_tika_extract_status_error(mock_tika: TikaMockConfigurator) -> None:
    # Arrange
    mock_tika(status=500, body="Internal Server Error")
    payload = (chunk for chunk in [b"chunk1"])

    # Act & Assert
    with pytest.raises(NetworkExtractionError) as exc_info:
        tika.extract_via_network(
            payload=payload,
            max_length=100,
            tika_url="http://localhost:9998",
            timeout_seconds=5.0,
            chunk_size=1024,
        )
    assert "error response" in str(exc_info.value)


def test_tika_extract_connection_error(mock_tika: TikaMockConfigurator) -> None:
    # Arrange
    mock_tika(body=requests.exceptions.ConnectionError("Connection refused"))
    payload = (chunk for chunk in [b"chunk1"])

    # Act & Assert
    with pytest.raises(NetworkExtractionError):
        tika.extract_via_network(
            payload=payload,
            max_length=100,
            tika_url="http://localhost:9998",
            timeout_seconds=5.0,
            chunk_size=1024,
        )


@pytest.mark.parametrize(
    "tika_url, mime_type, expected_url, expected_headers",
    [
        (
            "http://localhost:9998",
            None,
            "http://localhost:9998/tika",
            {"Accept": "text/plain"},
        ),
        (
            "http://localhost:9998/",
            "application/pdf",
            "http://localhost:9998/tika",
            {"Accept": "text/plain", "Content-Type": "application/pdf"},
        ),
        (
            "http://localhost:9998",
            "image/png",
            "http://localhost:9998/tika",
            {
                "Accept": "text/plain",
                "Content-Type": "image/png",
                "X-Tika-OCRLanguage": "heb+eng",
            },
        ),
    ],
    ids=[
        "no_mime_type_no_trailing_slash",
        "pdf_mime_type_with_trailing_slash",
        "image_mime_type_triggers_ocr_headers",
    ],
)
def test_prepare_request(
    tika_url: str,
    mime_type: str | None,
    expected_url: str,
    expected_headers: dict[str, str],
) -> None:
    # Act
    endpoint, headers = tika._prepare_request(tika_url, mime_type)

    # Assert
    assert endpoint == expected_url
    assert headers == expected_headers
