from typing import Final

from hermes.text_extraction.constants import TIKA_REMOTE_MIME_TYPES, MimeType
from hermes.text_extraction.core.extractors import docx, pdf, pptx, text, xlsx
from hermes.text_extraction.core.router import get_extractor_spec as router_get_extractor_spec
from hermes.text_extraction.core.spec import ExtractorSpec, PayloadMode
from hermes.text_extraction.shell import tika

EXTRACTION_REGISTRY: Final[dict[str, ExtractorSpec]] = {
    MimeType.PDF: ExtractorSpec(pdf.extract, PayloadMode.BUFFER),
    MimeType.DOCX: ExtractorSpec(docx.extract, PayloadMode.BUFFER),
    MimeType.XLSX: ExtractorSpec(xlsx.extract, PayloadMode.BUFFER),
    MimeType.PPTX: ExtractorSpec(pptx.extract, PayloadMode.BUFFER),
    MimeType.TEXT: ExtractorSpec(text.extract, PayloadMode.STREAM),
    **dict.fromkeys(
        TIKA_REMOTE_MIME_TYPES,
        ExtractorSpec(tika.extract_via_network, PayloadMode.STREAM, needs_tika_url=True),
    ),
}


def get_extractor_spec(mime_type: str) -> ExtractorSpec:
    """Retrieves the ExtractorSpec for the given MIME type from the global registry.

    Args:
        mime_type: The MIME type to look up.

    Returns:
        The registered ExtractorSpec.
    """
    return router_get_extractor_spec(mime_type, EXTRACTION_REGISTRY)
