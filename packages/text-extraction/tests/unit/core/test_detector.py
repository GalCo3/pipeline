import io
from unittest.mock import MagicMock

import pytest
from tests.mocks.fixtures import FiletypeMockConfigurator

from hermes.text_extraction.core import detector
from hermes.text_extraction.exceptions import ExtractionFailedError, StreamReadError


@pytest.mark.parametrize(
    "input_bytes, filetype_mime, expected_mime",
    [
        (b"dummy pdf data", "application/pdf", "application/pdf"),
        (b"dummy png data", "image/png", "image/png"),
        (b"This is plain text with no null bytes.", None, "text/plain"),
        (b"binary\x00data", None, "application/octet-stream"),
    ],
    ids=[
        "pdf_format",
        "png_format",
        "plain_text_fallback",
        "unknown_binary_fallback",
    ],
)
def test_detector_sniffs_formats(
    mock_filetype: FiletypeMockConfigurator,
    input_bytes: bytes,
    filetype_mime: str | None,
    expected_mime: str,
) -> None:
    # Arrange
    stream = io.BytesIO(input_bytes)

    if filetype_mime is not None:
        mock_kind = MagicMock()
        mock_kind.mime = filetype_mime
        mock_guess = mock_filetype(kind=mock_kind)
    else:
        mock_guess = mock_filetype(kind=None)

    # Act
    mime_type = detector.get_mime_type(stream)

    # Assert
    assert mime_type == expected_mime
    mock_guess.assert_called_once_with(input_bytes)
    assert stream.tell() == 0


def test_detector_handles_guess_exception(mock_filetype: FiletypeMockConfigurator) -> None:
    # Arrange
    input_bytes = b"some data"
    stream = io.BytesIO(input_bytes)
    mock_guess = mock_filetype(side_effect=ValueError("Guess error"))

    # Act
    mime_type = detector.get_mime_type(stream)

    # Assert
    assert mime_type == "application/octet-stream"
    mock_guess.assert_called_once_with(input_bytes)
    assert stream.tell() == 0


def test_detector_handles_read_exception(mock_filetype: FiletypeMockConfigurator) -> None:
    # Arrange
    class ErrorIO(io.BytesIO):
        def read(self, *args, **kwargs):
            raise RuntimeError("Disk read error")

    mock_guess = mock_filetype()

    # Act
    mime_type = detector.get_mime_type(ErrorIO())

    # Assert
    assert mime_type == "application/octet-stream"
    mock_guess.assert_not_called()


def test_exception_contract_attributes() -> None:
    # Arrange

    # Act
    e1 = StreamReadError(mime_type="test/mime")
    e2 = ExtractionFailedError(mime_type="test/mime")

    # Assert
    assert e1.mime_type == "test/mime"
    assert "Failed to read" in str(e1)
    assert e2.mime_type == "test/mime"
    assert "Text extraction failed" in str(e2)
