import io

import pytest

from hermes.text_extraction.exceptions import FileTooLargeError, StreamReadError
from hermes.text_extraction.shell import stream


def test_read_chunk_on_unrewindable(fake_unrewindable_stream_class):
    # Arrange
    raw = fake_unrewindable_stream_class(b"hello world")

    # Act
    result = stream.read_chunk(raw, 5)

    # Assert
    assert result == b"hello"
    with pytest.raises(io.UnsupportedOperation):
        raw.seek(0)
    assert raw.read() == b" world"


def test_read_into_memory_size_limit():
    # Arrange
    raw = io.BytesIO(b"0123456789")

    # Act & Assert
    with pytest.raises(FileTooLargeError) as exc_info:
        stream.read_into_memory(
            raw_stream=raw,
            max_size_bytes=5,
            initial_bytes=b"012",
            chunk_size=2,
        )
    assert "Stream exceeds maximum allowed size of 5 bytes." in str(exc_info.value)


def test_create_lazy_generator_size_limit():
    # Arrange
    raw = io.BytesIO(b"0123456789")
    gen = stream.create_lazy_generator(
        raw_stream=raw,
        initial_bytes=b"012",
        max_size_bytes=4,
        chunk_size=2,
    )

    # Act
    first_chunk = next(gen)

    # Assert
    assert first_chunk == b"012"
    with pytest.raises(FileTooLargeError) as exc_info:
        next(gen)
    assert "Stream exceeds maximum allowed size of 4 bytes." in str(exc_info.value)


def test_stream_read_os_error():
    # Arrange
    class ErrorStream(io.BytesIO):
        def read(self, *args, **kwargs):
            raise OSError("Simulated disk error")

    # Act & Assert
    with pytest.raises(StreamReadError):
        stream.read_chunk(ErrorStream(), 5)

    with pytest.raises(StreamReadError):
        stream.read_into_memory(ErrorStream(), 100, b"init", 5)


def test_read_into_memory_initial_size_limit():
    # Arrange
    raw = io.BytesIO(b"0123456789")

    # Act & Assert
    with pytest.raises(FileTooLargeError) as exc_info:
        stream.read_into_memory(
            raw_stream=raw,
            max_size_bytes=2,
            initial_bytes=b"a",
            chunk_size=2,
        )
    assert "Stream exceeds maximum allowed size of 2 bytes." in str(exc_info.value)


def test_create_lazy_generator_yields_loop_chunks():
    # Arrange
    raw = io.BytesIO(b"a" * 1000)
    gen = stream.create_lazy_generator(
        raw_stream=raw,
        initial_bytes=b"b" * 2000,
        max_size_bytes=5000,
        chunk_size=1000,
    )

    # Act
    chunks = list(gen)

    # Assert
    assert len(chunks) == 2
    assert chunks[0] == b"b" * 2000
    assert chunks[1] == b"a" * 1000
