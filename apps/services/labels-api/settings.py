from functools import lru_cache

from pydantic_settings import BaseSettings

from hermes.connections import BaseLLMConfig, BaseS3Config


class Settings(BaseSettings):
    cargo_config: BaseS3Config
    llm_config: BaseLLMConfig

    class Config:
        env_nested_delimiter = "__"


@lru_cache
def get_settings() -> Settings:
    return Settings()
