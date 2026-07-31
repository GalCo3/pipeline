import pytest

from hermes.text_extraction.core.router import get_extractor_spec
from hermes.text_extraction.core.spec import ExtractorSpec, PayloadMode
from hermes.text_extraction.exceptions import UnsupportedFormatError


def dummy_extractor(payload, max_length):
    return ""


def test_router_successfully_resolves_mapped_format():
    # Arrange
    spec = ExtractorSpec(fn=dummy_extractor, payload_mode=PayloadMode.BUFFER)
    registry = {"application/pdf": spec}

    # Act
    resolved_spec = get_extractor_spec("application/pdf", registry)

    # Assert
    assert resolved_spec is spec
    assert resolved_spec.payload_mode == PayloadMode.BUFFER


def test_router_raises_unsupported_format_error_for_unmapped_mime():
    # Arrange
    registry = {
        "application/pdf": ExtractorSpec(fn=dummy_extractor, payload_mode=PayloadMode.BUFFER)
    }

    # Act & Assert
    with pytest.raises(UnsupportedFormatError) as exc_info:
        get_extractor_spec("image/gif", registry)

    # Assert contract details
    assert exc_info.value.detected_mime_type == "image/gif"
    assert "Unsupported document format: 'image/gif'" in str(exc_info.value)
