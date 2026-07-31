import io
import logging
import re
from collections.abc import Generator

import docx
from docx.document import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from hermes.text_extraction.constants import MimeType
from hermes.text_extraction.core.decorators import log_extraction
from hermes.text_extraction.core.utils import join_chunks_with_limit
from hermes.text_extraction.exceptions import CorruptDocumentError

logger = logging.getLogger(__name__)


def _iter_block_items(doc: Document) -> Generator[Paragraph | Table]:
    """Iterate over paragraphs and tables in order of appearance in the document.

    Args:
        doc: The python-docx Document object.

    Yields:
        Paragraph or Table elements in structural order.
    """
    # sections
    for section in doc.sections:
        if section.header and not section.header.is_linked_to_previous:
            yield from section.header.iter_inner_content()
        if section.footer and not section.footer.is_linked_to_previous:
            yield from section.footer.iter_inner_content()

    # Paragraphs and tables
    yield from doc.iter_inner_content()


def _extract_item_text(item: Paragraph | Table) -> Generator[str]:
    """Extracts text chunks from a single block item (Paragraph or Table).

    Args:
        item: The Paragraph or Table block item.

    Yields:
        Extracted text chunks.
    """
    if isinstance(item, Paragraph):
        text = item.text.strip() if item.text else ""
        if text:
            yield text
    elif isinstance(item, Table):
        for row in item.rows:
            cells_text = [cell.text.strip() for cell in row.cells if cell.text]
            row_text = " | ".join(cells_text).strip()
            if row_text:
                yield row_text


@log_extraction(MimeType.DOCX)
def extract(payload: io.BytesIO, max_length: int) -> str:
    """python-docx DOM engine. Lazily iterates paragraphs and tables in order.

    Args:
        payload: In-memory byte buffer of the document.
        max_length: Maximum characters to yield.

    Returns:
        The extracted document text.
    """
    payload.seek(0)

    try:
        doc: Document = docx.Document(payload)
    except Exception as e:
        logger.error(
            "Document structure is corrupt",
            exc_info=True,
            extra={"mime_type": MimeType.DOCX},
        )
        raise CorruptDocumentError(MimeType.DOCX) from e

    chunks: Generator[str] = (
        chunk for item in _iter_block_items(doc) for chunk in _extract_item_text(item)
    )
    full_text: str = join_chunks_with_limit(
        chunks,
        max_length,
        mime_type=MimeType.DOCX,
        joiner="\n",
    )

    # substitute consecutive line feeds with a single line feed
    return re.sub(r"\n{2,}", "\n", full_text)
