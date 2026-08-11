from functools import cached_property
from typing import Annotated, Literal

from pydantic import BaseModel, FilePath, PositiveFloat, PositiveInt, model_validator
from pydantic_settings import NoDecode

from ..config_models.ssl import SSL


class BaseKafkaSecurityConfig(BaseModel, frozen=True):
    bootstrap_servers: str
    security_protocol: Literal["SSL", "PLAINTEXT"] = "SSL"
    ssl: SSL | None = None

    @model_validator(mode="after")
    def _require_ssl_for_ssl_protocol(self):
        if self.security_protocol == "SSL" and self.ssl is None:
            raise ValueError("ssl must be provided when security_protocol is 'SSL'")
        return self

    def get_settings(self) -> dict[str, str]:
        security: dict[str, str] = {"security.protocol": self.security_protocol}

        if self.ssl is not None:
            security.update(
                {
                    "ssl.ca.location": str(self.ssl.ca_path),
                    "ssl.certificate.location": str(self.ssl.cert_path),
                    "ssl.key.location": str(self.ssl.key_path),
                }
            )

        return security


class BaseProducerConfig(BaseKafkaSecurityConfig, frozen=True):
    retry_backoff_ms: PositiveInt = 3_000
    retry_backoff_max_ms: PositiveInt = 10_000
    retries: PositiveInt = 3
    flush_timeout: PositiveFloat = 3.0
    message_max_mb: PositiveInt = 1

    @cached_property
    def message_max_bytes(self):
        return self.message_max_mb * 1024 * 1024


class BaseConsumerConfig(BaseKafkaSecurityConfig, frozen=True):
    source_topics: Annotated[list[str], NoDecode]
    group_id: str
    auto_offset_reset: Literal["earliest", "latest"] = "earliest"
    enable_auto_commit: bool = False
    fetch_max_mb: PositiveInt = 1
    session_timeout_ms: PositiveInt = 60_000
    max_poll_interval_sec: PositiveInt = 3_600
    poll_timeout: PositiveFloat = 5.0
    liveness_file_path: str | None = "/tmp/heartbeat"

    @model_validator(mode="before")
    def split_source_topics(cls, values: dict):
        if isinstance(values.get("source_topics"), str):
            values["source_topics"] = [
                topic.strip() for topic in values["source_topics"].split(",")
            ]

        return values

    @cached_property
    def fetch_max_bytes(self):
        return self.fetch_max_mb * 1024 * 1024

    @cached_property
    def max_poll_interval_ms(self):
        return self.max_poll_interval_sec * 1000


class BaseAdminConfig(BaseKafkaSecurityConfig, frozen=True):
    pass


class BaseSchemaRegistryConfig(BaseModel, frozen=True):
    url: str
    access_key: str | None = None
    secret_key: str | None = None
    ssl_ca_location: FilePath | None = None

    @model_validator(mode="after")
    def _require_both_credentials(self):
        if (self.access_key is None) != (self.secret_key is None):
            raise ValueError("access_key and secret_key must be provided together")
        return self
