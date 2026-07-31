import pytest

from hermes.text_extraction.core.extractors import text
from hermes.text_extraction.exceptions import TextLimitExceededError


def test_text_extract_basic():
    # Arrange
    payload = [b"Hello ", b"world!"]

    # Act
    result = text.extract(payload, 100)

    # Assert
    assert result == "Hello world!"


def test_text_extract_limit_exceeded():
    # Arrange
    payload = [b"Hello ", b"world!"]

    # Act & Assert
    with pytest.raises(TextLimitExceededError):
        text.extract(payload, 5)


def test_text_extract_incomplete_utf8():
    # Arrange
    # \xe2 is the start of a 3-byte character, incomplete
    payload = [b"Hello ", b"\xe2"]

    # Act
    result = text.extract(payload, 100)

    # Assert
    # Incremental decoder replaces the incomplete trailing sequence on final flush
    assert result == "Hello \ufffd"


def test_text_extract_incomplete_utf8_boundary():
    # Arrange
    payload = [b"Hello ", b"\xe2"]

    # Act & Assert
    with pytest.raises(TextLimitExceededError):
        text.extract(payload, 6)


# =====================================================================
# Internal Helper Unit Tests
# =====================================================================


def test_iter_text_basic():
    # Arrange
    payload = [b"Hello ", b"world!"]

    # Act
    results = list(text._iter_text(payload))

    # Assert
    assert results == ["Hello ", "world!"]
