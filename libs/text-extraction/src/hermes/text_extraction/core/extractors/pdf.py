import io
import logging
from collections.abc import Generator

import pypdfium2 as pdfium

from hermes.text_extraction.constants import MimeType
from hermes.text_extraction.core.decorators import log_extraction
from hermes.text_extraction.core.utils import join_chunks_with_limit
from hermes.text_extraction.exceptions import CorruptDocumentError

logger = logging.getLogger(__name__)


def _iter_pdf(doc: pdfium.PdfDocument) -> Generator[str]:
    page: pdfium.PdfPage
    for page in doc:
        text_page: pdfium.PdfTextPage | None = None
        try:
            text_page = page.get_textpage()
            text: str = text_page.get_text_bounded()
            if text:
                yield text.strip()
        except Exception:
            continue
        finally:
            if text_page is not None:
                text_page.close()
            if page is not None:
                page.close()


@log_extraction(MimeType.PDF)
def extract(payload: io.BytesIO, max_length: int) -> str:
    """pypdfium2 low-overhead routine. Evaluates pages lazily.

    Args:
        payload: In-memory byte buffer of the PDF document.
        max_length: Maximum characters to yield.

    Returns:
        The extracted document text.
    """
    payload.seek(0)

    try:
        doc: pdfium.PdfDocument = pdfium.PdfDocument(payload)
    except Exception as exc:
        logger.error(
            "Document structure is corrupt",
            exc_info=True,
            extra={"mime_type": MimeType.PDF},
        )
        raise CorruptDocumentError(MimeType.PDF) from exc

    try:
        return join_chunks_with_limit(
            _iter_pdf(doc),
            max_length,
            mime_type=MimeType.PDF,
            joiner="\n",
        )
    finally:
        doc.close()
