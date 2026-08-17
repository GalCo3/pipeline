from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from hermes.connections import (
    BaseConsumerConfig,
    BaseElasticBasicConfig,
    BaseElasticCertConfig,
    BaseMongoConfig,
    BaseProducerConfig,
)


class ChiefConfig(BaseSettings):
    doc_path_template: str = Field(description="The URL template to fetch chief documents")
    api_key: SecretStr = Field(description="The API key for chief")
    timeout: int = Field(default=30, description="Timeout for chief requests in seconds")


class ChiefLexicalSettings(BaseSettings):
    consumer_config: BaseConsumerConfig
    # Cert auth in real deployments; basic auth for local/compose runs.
    elastic_config: BaseElasticCertConfig | BaseElasticBasicConfig
    mongo_config: BaseMongoConfig
    chief_config: ChiefConfig
    # Publishes a trigger message to `semantic_topic` after every successful
    # delete/update/index, for chief-semantic to consume.
    producer_config: BaseProducerConfig

    index_name: str = "chief-lexical"
    dls_collection: str = "dls"
    semantic_topic: str = "chief.semantic"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


def get_settings() -> ChiefLexicalSettings:
    return ChiefLexicalSettings()
