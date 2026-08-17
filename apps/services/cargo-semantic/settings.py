from functools import cache

from dotenv import find_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

from hermes.connections import (
    BaseConsumerConfig,
    BaseElasticBasicConfig,
    BaseElasticCertConfig,
    BaseMongoConfig,
)
from hermes.semantic_enrichment import (
    DEFAULT_CHUNK_OVERLAP_WORDS,
    DEFAULT_CHUNK_SIZE_WORDS,
    TritonConfig,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=find_dotenv("../.env", usecwd=True),
        env_nested_delimiter="__",
        extra="allow",
    )
    consumer_config: BaseConsumerConfig
    # Cert auth in real deployments; basic auth for local/compose runs.
    elastic_config: BaseElasticCertConfig | BaseElasticBasicConfig
    mongo_config: BaseMongoConfig
    triton_config: TritonConfig

    lexical_index_name: str
    semantic_index_name: str
    dls_collection: str = "dls"
    chunk_size: int = DEFAULT_CHUNK_SIZE_WORDS
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP_WORDS

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@cache
def get_settings() -> Settings:
    return Settings()
