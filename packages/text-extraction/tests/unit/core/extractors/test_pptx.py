import io
import zipfile

import pytest
from tests.fakes import FakePptx

from hermes.text_extraction.core.extractors import pptx
from hermes.text_extraction.exceptions import CorruptDocumentError, TextLimitExceededError


def test_pptx_extract():
    # Arrange
    payload = FakePptx().add_slide(["Powerpoint slide text content"]).build()

    # Act
    result = pptx.extract(payload, 100)

    # Assert
    assert result == "Powerpoint slide text content"


def test_pptx_extract_corrupt():
    # Arrange
    payload = io.BytesIO(b"corrupt-zip-structure")

    # Act & Assert
    with pytest.raises(CorruptDocumentError) as exc_info:
        pptx.extract(payload, 100)

    assert (
        exc_info.value.mime_type
        == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )


@pytest.mark.parametrize(
    "limit",
    [5, 10],
    ids=["limit_exceeded_5", "limit_boundary_10"],
)
def test_pptx_extract_limits(limit):
    # Arrange
    payload = FakePptx().add_slide(["Power", "Point"]).build()

    # Act & Assert
    with pytest.raises(TextLimitExceededError):
        pptx.extract(payload, limit)


# =====================================================================
# Internal Helper Unit Tests
# =====================================================================


def test_iter_pptx():
    # Arrange
    payload = (
        FakePptx()
        .add_slide(
            [
                ["Slide 1 Paragraph 1, Part 1 ", "Part 2"],
                "Slide 1 Paragraph 2",
                "",  # empty paragraph
            ]
        )
        .add_slide(["Slide 2 Paragraph 1"])
        .build()
    )

    # Act
    with zipfile.ZipFile(payload, "r") as zf_read:
        results = list(pptx._iter_pptx(zf_read, ["ppt/slides/slide1.xml", "ppt/slides/slide2.xml"]))

    # Assert
    assert results == [
        "Slide 1 Paragraph 1, Part 1 Part 2",
        "Slide 1 Paragraph 2",
        "Slide 2 Paragraph 1",
    ]


@pytest.mark.parametrize(
    "filename, expected_num",
    [
        ("ppt/slides/slide1.xml", 1),
        ("ppt/slides/slide12.xml", 12),
        ("slide3.xml", 3),
        ("slide.xml", 9999),
        ("slide_10_extra.xml", 10),
    ],
)
def test_get_slide_num(filename: str, expected_num: int) -> None:
    assert pptx._get_slide_num(filename) == expected_num
