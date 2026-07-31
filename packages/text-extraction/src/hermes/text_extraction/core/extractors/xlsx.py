import io
import logging
from collections.abc import Generator

import openpyxl
from openpyxl import Workbook

from hermes.text_extraction.constants import MimeType
from hermes.text_extraction.core.decorators import log_extraction
from hermes.text_extraction.core.utils import join_chunks_with_limit
from hermes.text_extraction.exceptions import CorruptDocumentError, TextLimitExceededError

logger = logging.getLogger(__name__)


def _iter_xlsx(wb: Workbook) -> Generator[str]:
    for sheet in wb.worksheets:
        for row in sheet.iter_rows(values_only=True):
            row_text: str = " ".join([str(cell) for cell in row if cell is not None])
            if row_text:
                yield row_text


@log_extraction(MimeType.XLSX)
def extract(payload: io.BytesIO, max_length: int) -> str:
    """openpyxl workbook consumer using read_only stream evaluation.

    Args:
        payload: In-memory byte buffer of the XLSX workbook.
        max_length: Maximum characters to yield.

    Returns:
        The extracted document text.
    """
    payload.seek(0)

    try:
        wb: Workbook = openpyxl.load_workbook(payload, data_only=True, read_only=True)
    except Exception as exc:
        logger.error(
            "Document structure is corrupt",
            exc_info=True,
            extra={"mime_type": MimeType.XLSX},
        )
        raise CorruptDocumentError(MimeType.XLSX) from exc

    try:
        return join_chunks_with_limit(
            _iter_xlsx(wb),
            max_length,
            mime_type=MimeType.XLSX,
            joiner="\n",
        )
    except TextLimitExceededError:
        raise
    except Exception as exc:
        logger.error(
            "Error occurred while iterating workbook sheets",
            exc_info=True,
            extra={"mime_type": MimeType.XLSX},
        )
        raise CorruptDocumentError(MimeType.XLSX) from exc
    finally:
        wb.close()
