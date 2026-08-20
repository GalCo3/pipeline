from functools import cache

from dotenv import find_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

from hermes.connections import (
    BaseConsumerConfig,
    BaseElasticBasicConfig,
    BaseElasticCertConfig,
    BaseMongoConfig,
    BaseS3Config,
    BaseTritonConfig,
)
from hermes.utils import DEFAULT_CHUNK_OVERLAP_TOKENS, DEFAULT_CHUNK_SIZE_TOKENS


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
    triton_config: BaseTritonConfig
    # Only set when the tokenizer comes from the `tokenizers` bucket rather
    # than a baked-in path or the HuggingFace Hub.
    s3_config: BaseS3Config | None = None

    lexical_index_name: str = "chief-lexical"
    semantic_index_name: str = "chief-semantic"
    dls_collection: str = "dls"
    embedding_model_name: str
    embedding_model_version: str = "1"
    # The tokenizer the embedding model was trained with: Triton serves raw ONNX
    # with no tokenizer of its own, so the service tokenizes and chunks with it.
    tokenizer_name_or_path: str
    chunk_size: int = DEFAULT_CHUNK_SIZE_TOKENS
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP_TOKENS

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@cache
def get_settings() -> Settings:
    return Settings()
