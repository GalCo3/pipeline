import io

import pytest
from tests.fakes import FakeWorkbook, FakeWorksheet
from tests.mocks import ExtractorMockConfigurator

from hermes.text_extraction.core.extractors import xlsx
from hermes.text_extraction.exceptions import CorruptDocumentError, TextLimitExceededError


def test_xlsx_extract(mock_openpyxl: ExtractorMockConfigurator) -> None:
    # Arrange
    fake_wb = FakeWorkbook(
        worksheets=[FakeWorksheet(rows=[["Stubbed", "Cell", "Values"], ["Another", "Row", None]])]
    )
    mock_class = mock_openpyxl(workbook=fake_wb)
    payload = io.BytesIO(b"xlsx-dummy-data")

    # Act
    result = xlsx.extract(payload, 100)

    # Assert
    assert result == "Stubbed Cell Values\nAnother Row"
    mock_class.assert_called_once_with(payload, data_only=True, read_only=True)
    fake_wb.close.assert_called_once()


def test_xlsx_extract_corrupt(mock_openpyxl: ExtractorMockConfigurator) -> None:
    # Arrange
    mock_openpyxl(side_effect=Exception("Failed to load workbook"))
    payload = io.BytesIO(b"corrupt-xlsx-data")

    # Act & Assert
    with pytest.raises(CorruptDocumentError) as exc_info:
        xlsx.extract(payload, 100)

    assert (
        exc_info.value.mime_type
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@pytest.mark.parametrize(
    "limit",
    [10, 30],
    ids=["limit_10", "limit_30"],
)
def test_xlsx_extract_max_length(mock_openpyxl: ExtractorMockConfigurator, limit: int) -> None:
    # Arrange
    fake_wb = FakeWorkbook(
        worksheets=[FakeWorksheet(rows=[["Stubbed", "Cell", "Values"], ["Another", "Row", None]])]
    )
    mock_openpyxl(workbook=fake_wb)
    payload = io.BytesIO(b"xlsx-dummy-data")

    # Act & Assert
    with pytest.raises(TextLimitExceededError):
        xlsx.extract(payload, limit)

    fake_wb.close.assert_called_once()


def test_xlsx_extract_iteration_failure(mock_openpyxl: ExtractorMockConfigurator) -> None:
    # Arrange
    fake_sheet = FakeWorksheet(side_effect=Exception("Workbook sheets iteration error"))
    fake_wb = FakeWorkbook(worksheets=[fake_sheet])
    mock_openpyxl(workbook=fake_wb)
    payload = io.BytesIO(b"xlsx-dummy-data")

    # Act & Assert
    with pytest.raises(CorruptDocumentError) as exc_info:
        xlsx.extract(payload, 100)

    assert (
        exc_info.value.mime_type
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    fake_wb.close.assert_called_once()


# =====================================================================
# Internal Helper Unit Tests
# =====================================================================


@pytest.mark.parametrize(
    "fake_wb, expected",
    [
        # 1. Single sheet with standard values
        (
            FakeWorkbook(
                worksheets=[FakeWorksheet(rows=[["Cell 1A", "Cell 1B"], ["Cell 2A", "Cell 2B"]])]
            ),
            ["Cell 1A Cell 1B", "Cell 2A Cell 2B"],
        ),
        # 2. Multiple worksheets
        (
            FakeWorkbook(
                worksheets=[
                    FakeWorksheet(rows=[["Sheet 1 Row 1"]]),
                    FakeWorksheet(rows=[["Sheet 2 Row 1"], ["Sheet 2 Row 2"]]),
                ]
            ),
            ["Sheet 1 Row 1", "Sheet 2 Row 1", "Sheet 2 Row 2"],
        ),
        # 3. Row with None values (empty cells)
        (
            FakeWorkbook(
                worksheets=[FakeWorksheet(rows=[[None, "Value 1", None, "Value 2", None]])]
            ),
            ["Value 1 Value 2"],
        ),
        # 4. Empty worksheet
        (
            FakeWorkbook(worksheets=[FakeWorksheet(rows=[])]),
            [],
        ),
    ],
    ids=["single_sheet", "multiple_sheets", "none_values", "empty_sheet"],
)
def test_iter_xlsx(fake_wb: FakeWorkbook, expected: list[str]) -> None:
    # Act
    results = list(xlsx._iter_xlsx(fake_wb))

    # Assert
    assert results == expected
