import ssl

import psycopg2
from psycopg2.extensions import connection
from psycopg2.pool import SimpleConnectionPool

from ..config_models.postgres import BasePostgresConfig
from ..config_models.ssl import SSL


def create_simple_postgres_connection(config: BasePostgresConfig) -> connection:
    if isinstance(config.auth, str):
        return psycopg2.connect(
            host=config.host,
            database=config.database,
            user=config.user,
            password=config.auth,
        )

    if isinstance(config.auth, SSL):
        ssl_context = ssl.create_default_context(
            ssl.Purpose.SERVER_AUTH, cafile=config.auth.ca_path
        )

        ssl_context.load_cert_chain(certfile=config.auth.cert_path, keyfile=config.auth.key_path)

        return psycopg2.connect(
            host=config.host,
            database=config.database,
            user=config.user,
            sslmode="verify-full",
            sslcert=config.auth.cert_path,
            sslkey=config.auth.key_path,
            sslrootcert=config.auth.ca_path,
        )

    raise ValueError("PostgreSQL auth type not supported")


def create_postgres_connection_pool(config: BasePostgresConfig) -> SimpleConnectionPool:
    if isinstance(config.auth, str):
        return SimpleConnectionPool(
            minconn=3,
            maxconn=20,
            host=config.host,
            database=config.database,
            user=config.user,
            password=config.auth,
        )

    if isinstance(config.auth, SSL):
        ssl_context = ssl.create_default_context(
            ssl.Purpose.SERVER_AUTH, cafile=config.auth.ca_path
        )

        ssl_context.load_cert_chain(certfile=config.auth.cert_path, keyfile=config.auth.key_path)

        return SimpleConnectionPool(
            minconn=3,
            maxconn=20,
            host=config.host,
            database=config.database,
            user=config.user,
            sslmode="verify-full",
            sslcert=config.auth.cert_path,
            sslkey=config.auth.key_path,
            sslrootcert=config.auth.ca_path,
        )

    raise ValueError("PostgreSQL auth type not supported")
