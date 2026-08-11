from functools import cache

from dotenv import find_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

from hermes.connections import (
    BaseConsumerConfig,
    BaseElasticBasicConfig,
    BaseElasticCertConfig,
    BaseMongoConfig,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=find_dotenv("../.env", usecwd=True),
        env_nested_delimiter="__",
        extra="allow",
    )
    consumer_config: BaseConsumerConfig
    elastic_config: BaseElasticCertConfig | BaseElasticBasicConfig
    mongo_config: BaseMongoConfig
    index_name: str
    dls_collection: str = "chat_lexical_dls"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@cache
def get_settings() -> Settings:
    return Settings()
