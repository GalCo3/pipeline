from http import HTTPStatus

from exceptions import CargoFileNotFoundError

from hermes.connections import BaseS3Handler
from hermes.observability import get_logger
from hermes.text_extraction import ExtractionResult, UnsupportedFormatError, extract_text
from hermes.text_extraction.config import AppSettings

logger = get_logger(__name__)


def extract_cargo_files_text(
    cargo_client: BaseS3Handler, s3_key: str, s3_bucket: str
) -> ExtractionResult | None:
    response, _ = cargo_client.get_file(s3_key, s3_bucket)

    if response.is_success:
        file = response.response["Body"]
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
        if response.error.response["Error"]["Code"] == "NoSuchKey":
            logger.warning("Cargo file not found in S3", status=HTTPStatus.NOT_FOUND)

            raise CargoFileNotFoundError("Cargo file not found in S3")

        raise response.error
