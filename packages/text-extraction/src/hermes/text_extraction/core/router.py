import logging
from collections.abc import Mapping

from hermes.text_extraction.core.spec import ExtractorSpec
from hermes.text_extraction.exceptions import UnsupportedFormatError

logger = logging.getLogger(__name__)


def get_extractor_spec(mime_type: str, registry: Mapping[str, ExtractorSpec]) -> ExtractorSpec:
    """Maps verified MIME structures to extractor specs via registry lookup.

    Args:
        mime_type: Detected MIME type of the stream.
        registry: Extractor registry mapping MIME types to specs.

    Returns:
        The matching ExtractorSpec.

    Raises:
        UnsupportedFormatError: If the MIME type is not registered.
    """
    logger.info(
        "Routing MIME type to registered extractor",
        extra={"mime_type": mime_type},
    )
    spec: ExtractorSpec | None = registry.get(mime_type)

    if spec is None:
        logger.error(
            "Unsupported MIME type encountered",
            extra={"mime_type": mime_type},
        )
        raise UnsupportedFormatError(mime_type)

    return spec
