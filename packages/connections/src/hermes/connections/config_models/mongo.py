from pydantic import BaseModel, FilePath, SecretStr


class MongoSSL(BaseModel, frozen=True):
    """x509 material for one node. pymongo takes a single PEM holding both the
    client cert and its key (``tlsCertificateKeyFile``), so no separate key."""

    ca_path: FilePath
    cert_path: FilePath


class X509Auth(BaseModel, frozen=True):
    """Cert-based (x509) auth. Per-node SSL material; remote required only for
    two-node setups."""

    local: MongoSSL
    remote: MongoSSL | None = None


class BasicAuth(BaseModel, frozen=True):
    """Username/password auth. Same credentials for local and remote."""

    username: str
    password: SecretStr


MongoAuth = X509Auth | BasicAuth


class BaseMongoConfig(BaseModel, frozen=True):
    local_host: str
    remote_host: str | None = None
    port: int = 27017
    database: str
    auth: MongoAuth
