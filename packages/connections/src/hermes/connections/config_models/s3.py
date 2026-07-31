from pydantic import BaseModel, PositiveInt


class BaseS3SiteConfig(BaseModel, frozen=True):
    endpoint: str
    access_key: str
    secret_key: str
    read_timeout_seconds: PositiveInt = 10


class BaseS3Config(BaseModel, frozen=True):
    local_site: BaseS3SiteConfig
    remote_site: BaseS3SiteConfig | None = None
