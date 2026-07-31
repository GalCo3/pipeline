import io
import logging
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Generator, Iterator
from typing import IO, Any

from hermes.text_extraction.constants import MimeType
from hermes.text_extraction.core.decorators import log_extraction
from hermes.text_extraction.core.utils import join_chunks_with_limit
from hermes.text_extraction.exceptions import CorruptDocumentError, TextLimitExceededError

logger = logging.getLogger(__name__)


def _get_slide_num(filename: str) -> int:
    """Extracts slide number from filename, falling back to 9999 if no digits exist."""
    digits: str = "".join(filter(str.isdigit, filename.split("/")[-1]))
    return int(digits) if digits else 9999


def _iter_pptx(zf: zipfile.ZipFile, slide_files: list[str]) -> Generator[str]:
    """Iterate through slide XML files and extract paragraph texts in order."""
    for slide_file in slide_files:
        with zf.open(slide_file) as slide_xml:
            yield from _iter_slide_paragraphs(slide_xml)


def _iter_slide_paragraphs(slide_xml: IO[bytes]) -> Generator[str]:
    """Iterates slide XML element tree, yielding clean paragraph texts."""
    context: Iterator[tuple[str, Any]] = ET.iterparse(slide_xml, events=("start", "end"))
    curr_paragraph_text: list[str] = []

    for event, elem in context:
        tag_name: str = elem.tag.split("}")[-1]

        if event == "start" and tag_name == "p":
            curr_paragraph_text = []
        elif event == "end":
            if tag_name == "t" and elem.text:
                curr_paragraph_text.append(elem.text)
            elif tag_name == "p":
                para_text: str = "".join(curr_paragraph_text).strip()
                if para_text:
                    yield para_text

                elem.clear()


@log_extraction(MimeType.PPTX)
def extract(payload: io.BytesIO, max_length: int) -> str:
    """PowerPoint native XML parser extracting paragraphs from slide tree.

    Args:
        payload: In-memory byte buffer of the PPTX document.
        max_length: Maximum characters to yield.

    Returns:
        The extracted document text.
    """
    payload.seek(0)

    try:
        with zipfile.ZipFile(payload, "r") as zf:
            # Locate all slide XML files and sort them to maintain logical reading order
            slide_files: list[str] = [
                f for f in zf.namelist() if f.startswith("ppt/slides/slide") and f.endswith(".xml")
            ]
            slide_files.sort(key=_get_slide_num)

            return join_chunks_with_limit(
                _iter_pptx(zf, slide_files),
                max_length,
                mime_type=MimeType.PPTX,
                joiner="\n",
            )
    except TextLimitExceededError:
        raise
    except Exception as exc:
        logger.error(
            "Document structure is corrupt",
            exc_info=True,
            extra={"mime_type": MimeType.PPTX},
        )
        raise CorruptDocumentError(MimeType.PPTX) from exc
