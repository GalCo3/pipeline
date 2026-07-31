from collections.abc import Iterable
from typing import Any
from unittest.mock import MagicMock

from openpyxl import Workbook


class FakeWorksheet(MagicMock):
    """A fake openpyxl Worksheet."""

    def __init__(
        self,
        rows: Iterable[Iterable[Any]] | None = None,
        side_effect: Exception | None = None,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self._rows = list(rows) if rows is not None else []
        self._side_effect = side_effect

    def iter_rows(self, **kwargs: Any) -> Iterable[Iterable[Any]]:
        if self._side_effect is not None:
            raise self._side_effect
        return self._rows


class FakeWorkbook(MagicMock):
    """A fake openpyxl Workbook."""

    def __init__(self, worksheets: list[FakeWorksheet] | None = None, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.__class__ = Workbook  # type: ignore[assignment]
        self.worksheets = worksheets or []
