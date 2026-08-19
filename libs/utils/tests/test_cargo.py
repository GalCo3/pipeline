import io
from unittest.mock import MagicMock

from hermes.text_extraction import ExtractionResult
from hermes.utils import extract_cargo_files_text


def test_extract_cargo_files_text_success(monkeypatch):
    monkeypatch.setenv("HERMES_TEXT_EXTRACTION__TIKA_SERVER_URL", "http://localhost:9998")
    mock_s3 = MagicMock()
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.response = {"Body": io.BytesIO(b"Hello world")}
    mock_s3.get_file.return_value = (mock_response, None)

    result = extract_cargo_files_text(mock_s3, "key.txt", "bucket")
    assert isinstance(result, ExtractionResult)
    assert result.text == "Hello world"
