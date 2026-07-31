import io


class FakeUnrewindableStream(io.BytesIO):
    """A fake unrewindable stream that raises UnsupportedOperation on seek."""

    def seek(self, offset, whence=0):
        raise io.UnsupportedOperation("Seek is not supported on this stream.")
