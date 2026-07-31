from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import responses

from tests.fakes.docx import FakeDocument, FakeParagraph
from tests.fakes.pdf import FakePdfDocument, FakePdfPage
from tests.fakes.xlsx import FakeWorkbook, FakeWorksheet

ExtractorMockConfigurator = Callable[..., MagicMock]
TikaMockConfigurator = Callable[..., responses.RequestsMock]
FiletypeMockConfigurator = Callable[..., MagicMock]


@pytest.fixture
def mock_pdfium() -> Generator[ExtractorMockConfigurator]:
    with patch("pypdfium2.PdfDocument") as mock_class:

        def _configure(
            document: FakePdfDocument | None = None,
            side_effect: Any | None = None,
        ) -> MagicMock:
            if side_effect is not None:
                mock_class.side_effect = side_effect
                return mock_class

            if document is None:
                document = FakePdfDocument(
                    pages=[
                        FakePdfPage("Stubbed PDF Page Text"),
                        FakePdfPage("Stubbed PDF Page Text"),
                    ]
                )

            mock_class.return_value = document
            return mock_class

        yield _configure


@pytest.fixture
def mock_openpyxl() -> Generator[ExtractorMockConfigurator]:
    with patch("openpyxl.load_workbook") as mock_class:

        def _configure(
            workbook: FakeWorkbook | None = None,
            side_effect: Any | None = None,
        ) -> MagicMock:
            if side_effect is not None:
                mock_class.side_effect = side_effect
                return mock_class

            if workbook is None:
                workbook = FakeWorkbook(
                    worksheets=[
                        FakeWorksheet(
                            rows=[["Stubbed", "Cell", "Values"], ["Another", "Row", None]]
                        )
                    ]
                )

            mock_class.return_value = workbook
            return mock_class

        yield _configure


@pytest.fixture
def mock_docx() -> Generator[ExtractorMockConfigurator]:
    with patch("docx.Document") as mock_class:

        def _configure(
            document: FakeDocument | None = None,
            side_effect: Any | None = None,
        ) -> MagicMock:
            if side_effect is not None:
                mock_class.side_effect = side_effect
                return mock_class

            if document is None:
                document = FakeDocument(
                    content=[
                        FakeParagraph("Stubbed Paragraph 1"),
                        FakeParagraph("Stubbed Paragraph 2"),
                    ]
                )

            mock_class.return_value = document
            return mock_class

        yield _configure


@pytest.fixture
def mock_tika() -> Generator[TikaMockConfigurator]:
    with responses.RequestsMock() as rsps:

        def _configure(
            body: str | bytes | Exception = "Hello Tika World!",
            status: int = 200,
            url: str = "http://localhost:9998/tika",
            method: str = responses.PUT,
        ) -> responses.RequestsMock:
            rsps.add(
                method,
                url,
                body=body,
                status=status,
            )
            return rsps

        yield _configure


@pytest.fixture
def mock_filetype() -> Generator[FiletypeMockConfigurator]:
    with patch("filetype.guess") as mock_class:

        def _configure(
            kind: Any | None = None,
            side_effect: Any | None = None,
        ) -> MagicMock:
            if side_effect is not None:
                mock_class.side_effect = side_effect
            else:
                mock_class.return_value = kind
            return mock_class

        yield _configure
