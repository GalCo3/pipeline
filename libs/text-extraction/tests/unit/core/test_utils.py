import pytest

from hermes.text_extraction.core.utils import join_chunks_with_limit
from hermes.text_extraction.exceptions import TextLimitExceededError


def test_join_chunks_with_limit_success():
    # Arrange
    chunks = ["hello", "world"]

    # Act
    result = join_chunks_with_limit(
        chunks,
        max_length=15,
        mime_type="text/plain",
        joiner=" ",
    )

    # Assert
    assert result == "hello world"


def test_join_chunks_with_limit_exceeded_in_loop():
    # Arrange
    chunks = ["hello", "world"]

    # Act & Assert
    with pytest.raises(TextLimitExceededError) as exc_info:
        join_chunks_with_limit(
            chunks,
            max_length=5,
            mime_type="text/plain",
            joiner=" ",
        )
    assert exc_info.value.mime_type == "text/plain"


def test_join_chunks_with_limit_exceeded_post_join():
    # Arrange
    class SneakyJoiner(str):
        def join(self, iterable):
            return "this string is way too long"

    chunks = ["a", "b"]

    # Act & Assert
    with pytest.raises(TextLimitExceededError) as exc_info:
        join_chunks_with_limit(
            chunks,
            max_length=10,
            mime_type="text/plain",
            joiner=SneakyJoiner(","),
        )
    assert exc_info.value.mime_type == "text/plain"


def test_join_chunks_with_limit_empty_chunks():
    # Arrange
    chunks = ["hello", "", "world"]

    # Act
    result = join_chunks_with_limit(
        chunks,
        max_length=15,
        mime_type="text/plain",
        joiner=" ",
    )

    # Assert
    assert result == "hello world"
