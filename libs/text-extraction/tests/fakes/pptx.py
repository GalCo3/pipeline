import io
import zipfile


class FakePptx:
    """A helper class to conveniently build in-memory PPTX slide deck payloads for testing."""

    def __init__(self) -> None:
        self.slides: list[list[str | list[str]]] = []

    def add_slide(self, paragraphs: list[str | list[str]]) -> FakePptx:
        self.slides.append(paragraphs)
        return self

    def build(self) -> io.BytesIO:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            for i, paragraphs in enumerate(self.slides, start=1):
                xml_content = self._build_slide_xml(paragraphs)
                zf.writestr(f"ppt/slides/slide{i}.xml", xml_content)
        buffer.seek(0)
        return buffer

    def _build_slide_xml(self, paragraphs: list[str | list[str]]) -> str:
        xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">\n'
            "<p:cSld><p:spTree><p:sp><p:txBody>"
        )
        for para in paragraphs:
            xml += "<a:p>"
            if isinstance(para, str):
                if para:  # only create run if not empty
                    xml += f"<a:r><a:t>{para}</a:t></a:r>"
            else:
                for run in para:
                    if run:
                        xml += f"<a:r><a:t>{run}</a:t></a:r>"
            xml += "</a:p>"
        xml += "</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
        return xml
