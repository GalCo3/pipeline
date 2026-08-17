from pydantic import BaseModel, PositiveInt


class BaseTritonSiteConfig(BaseModel, frozen=True):
    endpoint: str
    infer_token: str | None = None
    manage_token: str | None = None
    timeout_seconds: PositiveInt = 30
    verify_ssl: bool = False



class BaseTritonConfig(BaseModel, frozen=True):
    local_site: BaseTritonSiteConfig
    remote_site: BaseTritonSiteConfig | None = None
