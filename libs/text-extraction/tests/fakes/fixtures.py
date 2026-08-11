import io
import zipfile

import pytest

from tests.fakes.stream import FakeUnrewindableStream


@pytest.fixture
def fake_unrewindable_stream_class():
    return FakeUnrewindableStream


@pytest.fixture
def fake_docx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("word/document.xml", "dummy")
    return buffer.getvalue()


@pytest.fixture
def fake_xlsx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("xl/workbook.xml", "dummy")
    return buffer.getvalue()


@pytest.fixture
def fake_pptx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        slide_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">\n'
            "<p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r>"
            "<a:t>Powerpoint slide text content</a:t>"
            "</a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld>"
            "</p:sld>"
        )
        zf.writestr("ppt/slides/slide1.xml", slide_xml)
    return buffer.getvalue()


@pytest.fixture
def fake_corrupt_pptx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("ppt/presentation.xml", "corrupt-pptx-data")
    return buffer.getvalue()[:100]


@pytest.fixture
def fake_doc_bytes() -> bytes:
    buf = bytearray(516)
    buf[0:8] = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    buf[512:516] = b"\xec\xa5\xc1\x00"
    return bytes(buf)
