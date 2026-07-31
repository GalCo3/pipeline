from collections.abc import Iterable
from typing import Any
from unittest.mock import MagicMock


class FakePdfTextPage(MagicMock):
    """A fake pdfium PdfTextPage."""

    def __init__(self, text: str = "", *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._text = text

    def get_text_bounded(self, *args: Any, **kwargs: Any) -> str:
        return self._text

    def _get_child_mock(self, /, **kwargs: Any) -> Any:
        return MagicMock(**kwargs)


class FakePdfPage(MagicMock):
    """A fake pdfium PdfPage."""

    def __init__(
        self,
        text_or_exception: str | Exception | type[BaseException] = "",
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        if isinstance(text_or_exception, Exception) or (
            isinstance(text_or_exception, type) and issubclass(text_or_exception, BaseException)
        ):
            if isinstance(text_or_exception, type):
                self.get_textpage.side_effect = text_or_exception()
            else:
                self.get_textpage.side_effect = text_or_exception
        else:
            self.get_textpage.return_value = FakePdfTextPage(text=text_or_exception)

    def _get_child_mock(self, /, **kwargs: Any) -> Any:
        return MagicMock(**kwargs)


class FakePdfDocument(MagicMock):
    """A fake pdfium PdfDocument."""

    def __init__(
        self,
        pages: Iterable[FakePdfPage] | None = None,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self._pages = list(pages) if pages is not None else []
        self.__iter__.side_effect = lambda: iter(self._pages)

    def _get_child_mock(self, /, **kwargs: Any) -> Any:
        return MagicMock(**kwargs)
