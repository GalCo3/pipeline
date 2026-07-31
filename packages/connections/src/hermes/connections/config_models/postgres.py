from pydantic import BaseModel

from ..config_models.ssl import SSL


class BasePostgresConfig(BaseModel, frozen=True):
    host: str
    database: str
    user: str
    auth: str | SSL
    port: int = 5432
