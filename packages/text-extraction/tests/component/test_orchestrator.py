from typing import Any

import pypdfium2 as pdfium
import pytest
import requests
from docx.opc.exceptions import PackageNotFoundError

from hermes.text_extraction.exceptions import (
    CorruptDocumentError,
    ExtractionFailedError,
    FileTooLargeError,
    NetworkExtractionError,
    TextLimitExceededError,
    UnsupportedFormatError,
)
from hermes.text_extraction.orchestrator import extract_text
from tests.utils import create_settings

# =====================================================================
# Successful Format Extraction Tests
# =====================================================================


@pytest.mark.parametrize(
    "file_bytes_or_fixture, expected_result, mock_fixture_name, mock_args",
    [
        (b"Incremental text content", "Incremental text content", None, {}),
        (
            b"%PDF-1.4\ncontent-data",
            "Stubbed PDF Page Text\nStubbed PDF Page Text",
            "mock_pdfium",
            {},
        ),
        ("fake_docx_bytes", "Stubbed Paragraph 1\nStubbed Paragraph 2", "mock_docx", {}),
        ("fake_xlsx_bytes", "Stubbed Cell Values\nAnother Row", "mock_openpyxl", {}),
        ("fake_pptx_bytes", "Powerpoint slide text content", None, {}),
        (
            b"\x89PNG\r\n\x1a\n",
            "Stubbed OCR Image Text",
            "mock_tika",
            {"body": "Stubbed OCR Image Text"},
        ),
        (
            "fake_doc_bytes",
            "Stubbed Legacy DOC Text",
            "mock_tika",
            {"body": "Stubbed Legacy DOC Text"},
        ),
    ],
    ids=[
        "plain_text",
        "pdf",
        "docx",
        "xlsx",
        "pptx",
        "image_ocr",
        "legacy_doc",
    ],
)
def test_orchestrator_successful_extraction(
    request: pytest.FixtureRequest,
    fake_unrewindable_stream_class: Any,
    file_bytes_or_fixture: bytes | str,
    expected_result: str,
    mock_fixture_name: str | None,
    mock_args: dict[str, Any],
) -> None:
    # Arrange
    if mock_fixture_name:
        mock_configurator = request.getfixturevalue(mock_fixture_name)
        mock_configurator(**mock_args)

    if isinstance(file_bytes_or_fixture, str):
        file_bytes = request.getfixturevalue(file_bytes_or_fixture)
    else:
        file_bytes = file_bytes_or_fixture

    settings = create_settings(max_text_length=100)
    stream = fake_unrewindable_stream_class(file_bytes)

    # Act
    result = extract_text(stream, settings)

    # Assert
    assert result == expected_result


# =====================================================================
# Ingress Validation & Limit Tests
# =====================================================================


def test_orchestrator_text_limit_exceeded(fake_unrewindable_stream_class: Any) -> None:
    # Arrange
    settings = create_settings(max_text_length=10)
    data = b"Hello, Hermes text extractor!"
    stream = fake_unrewindable_stream_class(data)

    # Act & Assert
    with pytest.raises(TextLimitExceededError):
        extract_text(stream, settings)


def test_orchestrator_file_too_large(fake_unrewindable_stream_class: Any) -> None:
    # Arrange
    settings = create_settings(max_text_length=15000)
    settings.max_file_size_bytes = 10000  # greater than peek size
    data = b"a" * 12000
    stream = fake_unrewindable_stream_class(data)

    # Act & Assert
    with pytest.raises(FileTooLargeError):
        extract_text(stream, settings)


def test_orchestrator_unsupported_format(fake_unrewindable_stream_class: Any) -> None:
    # Arrange
    settings = create_settings(max_text_length=100)
    data = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    stream = fake_unrewindable_stream_class(data)

    # Act & Assert
    with pytest.raises(UnsupportedFormatError):
        extract_text(stream, settings)


# =====================================================================
# Parser and Network Error Mappings
# =====================================================================


@pytest.mark.parametrize(
    "file_bytes_or_fixture, mock_fixture_name, mock_args, expected_exception",
    [
        (
            "fake_docx_bytes",
            "mock_docx",
            {"side_effect": PackageNotFoundError("Corrupted package structure")},
            CorruptDocumentError,
        ),
        (
            b"%PDF-1.4\ncorrupt-pdf-data",
            "mock_pdfium",
            {"side_effect": pdfium.PdfiumError("Failed to load PDF document")},
            CorruptDocumentError,
        ),
        (
            "fake_xlsx_bytes",
            "mock_openpyxl",
            {"side_effect": Exception("File is not a zip file")},
            CorruptDocumentError,
        ),
        (
            "fake_corrupt_pptx_bytes",
            None,
            {},
            CorruptDocumentError,
        ),
        (
            b"\x89PNG\r\n\x1a\ncorrupt-image-data",
            "mock_tika",
            {"status": 500, "body": "Internal Server Error"},
            NetworkExtractionError,
        ),
        (
            "fake_doc_bytes",
            "mock_tika",
            {"body": requests.exceptions.Timeout("Connection timed out")},
            NetworkExtractionError,
        ),
    ],
    ids=["docx", "pdf", "xlsx", "pptx", "image", "legacy_doc"],
)
def test_orchestrator_corrupt_files(
    request: pytest.FixtureRequest,
    fake_unrewindable_stream_class: Any,
    file_bytes_or_fixture: bytes | str,
    mock_fixture_name: str | None,
    mock_args: dict[str, Any],
    expected_exception: type[Exception],
) -> None:
    # Arrange
    if mock_fixture_name:
        mock_configurator = request.getfixturevalue(mock_fixture_name)
        mock_configurator(**mock_args)

    if isinstance(file_bytes_or_fixture, str):
        file_bytes = request.getfixturevalue(file_bytes_or_fixture)
    else:
        file_bytes = file_bytes_or_fixture

    # For docx/xlsx, we truncate the bytes to simulate corrupt zip structure
    if mock_fixture_name in ("mock_docx", "mock_openpyxl"):
        file_bytes = file_bytes[:100]

    settings = create_settings(max_text_length=100)
    stream = fake_unrewindable_stream_class(file_bytes)

    # Act & Assert
    with pytest.raises(expected_exception):
        extract_text(stream, settings)


def test_orchestrator_unexpected_internal_error(
    fake_unrewindable_stream_class: Any, mock_pdfium: Any
) -> None:
    # Arrange
    mock_class = mock_pdfium()
    mock_class.return_value.close.side_effect = ValueError("Unexpected internal failure")
    settings = create_settings(max_text_length=100)
    stream = fake_unrewindable_stream_class(b"%PDF-1.4\ncontent")

    # Act & Assert
    with pytest.raises(ExtractionFailedError):
        extract_text(stream, settings)
