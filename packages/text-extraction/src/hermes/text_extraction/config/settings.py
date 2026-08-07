from dotenv import find_dotenv
from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from hermes.text_extraction.constants import (
    BYTES_IN_MB,
    DEFAULT_CHUNK_SIZE_BYTES,
    DEFAULT_MAX_FILE_SIZE_MB,
    DEFAULT_MAX_TEXT_LENGTH_MB,
    DEFAULT_NETWORK_TIMEOUT_SECONDS,
    ENV_PREFIX,
    HEADER_READ_SIZE_BYTES,
)


class AppSettings(BaseSettings):
    max_file_size_bytes: int = Field(
        default=DEFAULT_MAX_FILE_SIZE_MB, gt=0, validate_default=True, alias="MAX_FILE_SIZE_MB"
    )
    max_text_length: int = Field(
        default=DEFAULT_MAX_TEXT_LENGTH_MB, gt=0, validate_default=True, alias="MAX_TEXT_LENGTH_MB"
    )
    chunk_size_bytes: int = Field(default=DEFAULT_CHUNK_SIZE_BYTES, gt=0)
    network_timeout_seconds: float = Field(default=DEFAULT_NETWORK_TIMEOUT_SECONDS, gt=0)
    tika_server_url: HttpUrl

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_file=find_dotenv(".env"),
        env_nested_delimiter="__",
        env_prefix_target="all",
        extra="allow",
    )

    @field_validator("max_file_size_bytes", "max_text_length", mode="after")
    @classmethod
    def convert_mb_to_bytes(cls, value: int) -> int:
        bytes_val = value * BYTES_IN_MB
        if bytes_val < HEADER_READ_SIZE_BYTES:
            raise ValueError(
                f"value ({bytes_val}) must be at least "
                f"HEADER_READ_SIZE_BYTES ({HEADER_READ_SIZE_BYTES})"
            )
        return bytes_val
