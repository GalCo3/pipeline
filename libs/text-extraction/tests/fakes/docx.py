from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

from docx.table import Table
from docx.text.paragraph import Paragraph


class FakeParagraph(MagicMock):
    """A fake docx Paragraph."""

    def __init__(self, text: str = "", *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.__class__ = Paragraph  # type: ignore[assignment]
        self.text = text


class FakeTable(MagicMock):
    """A fake docx Table."""

    def __init__(self, rows: list[list[str]] | None = None, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.__class__ = Table  # type: ignore[assignment]
        mock_rows = []
        for cell_texts in rows or []:
            mock_row = MagicMock()
            mock_cells = []
            for cell_text in cell_texts:
                mock_cell = MagicMock()
                mock_cell.text = cell_text
                mock_cells.append(mock_cell)
            mock_row.cells = mock_cells
            mock_rows.append(mock_row)
        self.rows = mock_rows


class FakeHeaderFooter(MagicMock):
    """A fake docx Header or Footer."""

    def __init__(
        self,
        content: list[FakeParagraph | FakeTable] | None = None,
        is_linked_to_previous: bool = False,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.is_linked_to_previous = is_linked_to_previous
        self._content = content or []

    def iter_inner_content(self) -> Generator[FakeParagraph | FakeTable]:
        yield from self._content


class FakeSection(MagicMock):
    """A fake docx Section."""

    def __init__(
        self,
        header: FakeHeaderFooter | None = None,
        footer: FakeHeaderFooter | None = None,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.header = header or FakeHeaderFooter()
        self.footer = footer or FakeHeaderFooter()


class FakeDocument(MagicMock):
    """A fake docx Document."""

    def __init__(
        self,
        content: list[FakeParagraph | FakeTable] | None = None,
        sections: list[FakeSection] | None = None,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self._content = content or []
        self.sections = sections or []

    def iter_inner_content(self) -> Generator[FakeParagraph | FakeTable]:
        yield from self._content
