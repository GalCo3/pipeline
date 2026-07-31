import logging

from pymongo import AsyncMongoClient, MongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.synchronous.database import Database

from ..config_models.mongo import BaseMongoConfig, BasicAuth, X509Auth

logger = logging.getLogger(__name__)

MongoConfig = BaseMongoConfig

# Re-exported so callers depend on the driver through the lib, not pymongo
# directly (the lib owns the Mongo driver choice: pymongo's native async client).
__all__ = [
    "AsyncDatabase",
    "AsyncMongoClient",
    "Database",
    "MongoClient",
    "MongoConfig",
    "create_async_mongo_clients",
    "create_mongo_clients",
]


def _client_kwargs(config: MongoConfig, is_local_client: bool) -> dict:
    host = config.local_host if is_local_client else config.remote_host
    kwargs: dict = {"host": host, "port": config.port}

    match config.auth:
        case X509Auth() as auth:
            ssl = auth.local if is_local_client else auth.remote
            if ssl is None:
                raise ValueError("auth.remote must be set for cert-based remote connections")
            kwargs.update(
                tls=True,
                tlsCAFile=str(ssl.ca_path),
                tlsCertificateKeyFile=str(ssl.cert_path),
                # TLS alone only encrypts the transport; without an explicit
                # mechanism pymongo never authenticates and the server rejects
                # every command with "requires authentication" (code 13).
                authMechanism="MONGODB-X509",
                authSource="$external",
            )
        case BasicAuth() as auth:
            kwargs.update(
                username=auth.username,
                password=auth.password.get_secret_value(),
                authSource="admin",
            )

    return kwargs


def _has_remote(config: MongoConfig) -> bool:
    return getattr(config, "remote_host", None) is not None


def _create_raw_client(config: MongoConfig, is_local_client: bool) -> MongoClient:
    return MongoClient(**_client_kwargs(config, is_local_client))


def _create_raw_async_client(config: MongoConfig, is_local_client: bool) -> AsyncMongoClient:
    return AsyncMongoClient(**_client_kwargs(config, is_local_client))


def create_mongo_clients(
    config: MongoConfig,
) -> tuple[MongoClient, MongoClient | None]:
    """
    Create local and remote (if exists) synchronous MongoDB clients.

    :param config: Configuration object containing the necessary settings for the
        MongoDB clients.

    :return: A tuple containing the local MongoClient and the remote MongoClient
        (if exists).
    """
    local_client: MongoClient = _create_raw_client(config, is_local_client=True)
    remote_client: MongoClient | None = None

    logger.info(msg="Created local MongoDB client", extra=config.__dict__)

    if _has_remote(config):
        remote_client = _create_raw_client(config, is_local_client=False)

        logger.info(msg="Created remote MongoDB client", extra=config.__dict__)

    return local_client, remote_client


def create_async_mongo_clients(
    config: MongoConfig,
) -> tuple[AsyncMongoClient, AsyncMongoClient | None]:
    local_client: AsyncMongoClient = _create_raw_async_client(config, is_local_client=True)
    remote_client: AsyncMongoClient | None = None

    logger.info(msg="Created local async MongoDB client", extra=config.__dict__)

    if _has_remote(config):
        remote_client = _create_raw_async_client(config, is_local_client=False)

        logger.info(msg="Created remote async MongoDB client", extra=config.__dict__)

    return local_client, remote_client
