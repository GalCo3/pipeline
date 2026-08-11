from pydantic import BaseModel, PositiveInt, SecretStr

from ..config_models.ssl import SSL


class BaseElasticConfig(BaseModel, frozen=True):
    local_host: str
    remote_host: str | None = None
    request_timeout: PositiveInt = 30
    max_retries: PositiveInt = 3


class BaseElasticCertConfig(BaseElasticConfig, frozen=True):
    local_auth: SSL
    remote_auth: SSL | None = None


class BaseElasticJWTConfig(BaseElasticConfig, frozen=True):
    jwt: str


class BaseElasticBasicConfig(BaseElasticConfig, frozen=True):
    username: str
    password: SecretStr
