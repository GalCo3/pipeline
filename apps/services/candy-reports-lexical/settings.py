from pydantic_settings import BaseSettings, SettingsConfigDict

from hermes.connections import (
    BaseConsumerConfig,
    BaseElasticBasicConfig,
    BaseElasticCertConfig,
    BaseMongoConfig,
)


class CandyReportsLexicalSettings(BaseSettings):
    consumer_config: BaseConsumerConfig
    elastic_config: BaseElasticCertConfig | BaseElasticBasicConfig
    mongo_config: BaseMongoConfig

    index_name: str = "candy-reports-lexical"
    dls_collection: str = "dls"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


def get_settings() -> CandyReportsLexicalSettings:
    return CandyReportsLexicalSettings()
