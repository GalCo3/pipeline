from http import HTTPStatus

from botocore.exceptions import ClientError

from hermes.connections import BaseS3Handler, S3Error
from hermes.observability import get_logger
from hermes.text_extraction import ExtractionResult, UnsupportedFormatError, extract_text
from hermes.text_extraction.config import AppSettings

logger = get_logger(__name__)


class CargoFileNotFoundError(Exception):
    """Raised when a cargo file is missing from S3."""


def extract_cargo_files_text(
    cargo_client: BaseS3Handler, s3_key: str, s3_bucket: str
) -> ExtractionResult | None:
    """Fetch file from S3 and extract text using hermes text-extraction."""
    response, _ = cargo_client.get_file(s3_key, s3_bucket)

    if response.is_success:
        file = (response.response or {})["Body"]
        try:
            return extract_text(file, AppSettings())
        except UnsupportedFormatError as e:
            logger.warning(
                "Unsupported file format for text extraction, skipping message",
                err_message=str(e),
                mime_type=e.mime_type,
            )
            return None
    else:
        # SiteResponse.error is loosely typed (Exception | str | None), so the
        # botocore error code is only reachable through a real ClientError.
        error = response.error
        if isinstance(error, ClientError) and error.response["Error"]["Code"] == "NoSuchKey":
            logger.warning("Cargo file not found in S3", status=HTTPStatus.NOT_FOUND)
            raise CargoFileNotFoundError("Cargo file not found in S3")

        if isinstance(error, Exception):
            raise error

        raise S3Error({"message": "Failed to fetch cargo file from S3", "error": str(error)})
