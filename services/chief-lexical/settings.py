from hermes.connections import (
    BaseConsumerConfig,
    BaseElasticConfig,
    BaseMongoConfig,
)
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChiefConfig(BaseSettings):
    doc_path_template: str = Field(description="The URL template to fetch chief documents")
    api_key: SecretStr = Field(description="The API key for chief")
    timeout: int = Field(default=30, description="Timeout for chief requests in seconds")


class ChiefLexicalSettings(BaseSettings):
    consumer_config: BaseConsumerConfig
    elastic_config: BaseElasticConfig
    mongo_config: BaseMongoConfig
    chief_config: ChiefConfig

    index_name: str = "chief-lexical"
    dls_collection: str = "chief_lexical_dls"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )


def get_settings() -> ChiefLexicalSettings:
    return ChiefLexicalSettings()
