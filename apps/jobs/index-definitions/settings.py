from enum import StrEnum
from functools import cache

from dotenv import find_dotenv
from hermes.connections import BaseElasticBasicConfig, BaseElasticCertConfig
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    NP = "np"
    PREP = "prep"
    PROD = "prod"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=find_dotenv("../.env", usecwd=True),
        env_nested_delimiter="__",
        extra="allow",
    )
    # Cert auth in real deployments; basic auth for local/compose runs.
    elastic_config: BaseElasticCertConfig | BaseElasticBasicConfig
    environment: Environment


@cache
def get_settings() -> Settings:
    return Settings()
