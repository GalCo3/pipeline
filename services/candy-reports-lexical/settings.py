from pydantic_settings import BaseSettings, SettingsConfigDict

from hermes.connections import (
    BaseConsumerConfig,
    BaseElasticConfig,
    BaseMongoConfig,
)


class CandyReportsLexicalSettings(BaseSettings):
    consumer_config: BaseConsumerConfig
    elastic_config: BaseElasticConfig
    mongo_config: BaseMongoConfig

    index_name: str = "candy-reports-lexical"
    dls_collection: str = "candy_reports_lexical_dls"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )


def get_settings() -> CandyReportsLexicalSettings:
    return CandyReportsLexicalSettings()
