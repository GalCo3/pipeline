import io

import pypdfium2 as pdfium
import pytest
from tests.fakes import FakePdfDocument, FakePdfPage
from tests.mocks import ExtractorMockConfigurator

from hermes.text_extraction.core.extractors import pdf
from hermes.text_extraction.exceptions import CorruptDocumentError, TextLimitExceededError


def test_pdf_extract(mock_pdfium: ExtractorMockConfigurator) -> None:
    # Arrange
    fake_doc = FakePdfDocument(
        pages=[
            FakePdfPage("Stubbed PDF Page Text"),
            FakePdfPage("Stubbed PDF Page Text"),
        ]
    )
    mock_class = mock_pdfium(document=fake_doc)
    payload = io.BytesIO(b"pdf-dummy-data")

    # Act
    result = pdf.extract(payload, 100)

    # Assert
    assert result == "Stubbed PDF Page Text\nStubbed PDF Page Text"
    mock_class.assert_called_once_with(payload)
    fake_doc.close.assert_called_once()

    # Verify closing of pages and text pages
    for page in fake_doc:
        page.close.assert_called_once()
        page.get_textpage.return_value.close.assert_called_once()


def test_pdf_extract_corrupt(mock_pdfium: ExtractorMockConfigurator) -> None:
    # Arrange
    mock_pdfium(side_effect=pdfium.PdfiumError("Failed to load PDF"))
    payload = io.BytesIO(b"corrupt-pdf-data")

    # Act & Assert
    with pytest.raises(CorruptDocumentError) as exc_info:
        pdf.extract(payload, 100)

    assert exc_info.value.mime_type == "application/pdf"


@pytest.mark.parametrize(
    "limit, expected_pages_read",
    [
        (10, 1),
        (42, 2),
    ],
    ids=["fail_on_first_page", "fail_on_second_page"],
)
def test_pdf_extract_max_length(
    mock_pdfium: ExtractorMockConfigurator,
    limit: int,
    expected_pages_read: int,
) -> None:
    # Arrange
    fake_doc = FakePdfDocument(
        pages=[
            FakePdfPage("Stubbed PDF Page Text"),
            FakePdfPage("Stubbed PDF Page Text"),
        ]
    )
    mock_pdfium(document=fake_doc)
    payload = io.BytesIO(b"pdf-dummy-data")

    # Act & Assert
    with pytest.raises(TextLimitExceededError):
        pdf.extract(payload, limit)

    # Assert document was closed
    fake_doc.close.assert_called_once()

    # Assert pages and text pages were closed for the pages that were read
    mock_pages = list(fake_doc)
    for i in range(expected_pages_read):
        page = mock_pages[i]
        page.close.assert_called_once()
        page.get_textpage.return_value.close.assert_called_once()

    # Verify that the unread page (if any) was never closed or accessed
    for i in range(expected_pages_read, len(mock_pages)):
        page = mock_pages[i]
        page.close.assert_not_called()


# =====================================================================
# Internal Helper Unit Tests
# =====================================================================


def test_iter_pdf_yields_clean_text() -> None:
    # Arrange
    fake_doc = FakePdfDocument(
        pages=[
            FakePdfPage("Stubbed PDF Page Text"),
            FakePdfPage("Stubbed PDF Page Text"),
        ]
    )

    # Act
    results = list(pdf._iter_pdf(fake_doc))

    # Assert
    assert results == ["Stubbed PDF Page Text", "Stubbed PDF Page Text"]

    # Verify closing of pages and text pages
    for page in fake_doc:
        page.close.assert_called_once()
        page.get_textpage.return_value.close.assert_called_once()


def test_iter_pdf_handles_page_failure() -> None:
    # Arrange
    fake_doc = FakePdfDocument(
        pages=[
            FakePdfPage(ValueError("Parsing error")),
            FakePdfPage("Stubbed PDF Page Text"),
        ]
    )

    # Act
    results = list(pdf._iter_pdf(fake_doc))

    # Assert
    assert results == ["Stubbed PDF Page Text"]
