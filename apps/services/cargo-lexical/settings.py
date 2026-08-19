from functools import cache

from dotenv import find_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

from hermes.connections import (
    BaseConsumerConfig,
    BaseElasticBasicConfig,
    BaseElasticCertConfig,
    BaseMongoConfig,
    BaseProducerConfig,
    BaseS3Config,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=find_dotenv("../.env", usecwd=True),
        env_nested_delimiter="__",
        extra="allow",
    )
    consumer_config: BaseConsumerConfig
    cargo_config: BaseS3Config
    # Cert auth in real deployments; basic auth for local/compose runs.
    elastic_config: BaseElasticCertConfig | BaseElasticBasicConfig
    mongo_config: BaseMongoConfig
    # Publishes a trigger message to `semantic_topic` after every successful
    # delete/update/index, for cargo-semantic to consume.
    producer_config: BaseProducerConfig
    index_name: str
    dls_collection: str = "dls"
    semantic_topic: str = "cargo.semantic"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@cache
def get_settings() -> Settings:
    return Settings()
