import logging
import socket
import threading
from typing import ClassVar

from psycopg2 import OperationalError
from psycopg2.pool import SimpleConnectionPool

from ..config_models.postgres import BasePostgresConfig
from ..factories.postgres import (
    create_postgres_connection_pool,
    create_simple_postgres_connection,
)

logger = logging.getLogger(__name__)


def handle_postgres_exceptions(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except socket.gaierror as e:
            logger.exception("Postgres service is down")

            raise OperationalError("Error connecting to PostgreSQL") from e

    return wrapper


class PostgresContext:
    _conn_pool: ClassVar[SimpleConnectionPool | None] = None
    _lock: ClassVar = threading.Lock()

    def __init__(self, enable_transaction: bool, conn, cursor):
        self.enable_transaction = enable_transaction
        self.conn = conn
        self.cursor = cursor

    def __enter__(self):
        if self.enable_transaction:
            self.conn.autocommit = False

        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.enable_transaction:
                if exc_type is not None:
                    self.conn.rollback()
                else:
                    self.conn.commit()
        finally:
            self.cursor.close()
            self.conn.close()
            assert self._conn_pool is not None
            self._conn_pool.putconn(self.conn)

    @classmethod
    @handle_postgres_exceptions
    def create_conn_pool(cls, config: BasePostgresConfig):
        with cls._lock:
            if cls._conn_pool is None:
                cls._conn_pool = create_postgres_connection_pool(config)

    @classmethod
    @handle_postgres_exceptions
    def create(cls, enable_transaction: bool, config: BasePostgresConfig):
        cls.create_conn_pool(config)
        assert cls._conn_pool is not None
        conn = cls._conn_pool.getconn()
        cursor = conn.cursor()

        return PostgresContext(enable_transaction=enable_transaction, conn=conn, cursor=cursor)

    @classmethod
    def close(cls):
        with cls._lock:
            if cls._conn_pool is not None:
                cls._conn_pool.closeall()
                cls._conn_pool = None


class SimplePostgresContext:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()

    @classmethod
    @handle_postgres_exceptions
    def create(cls, config: BasePostgresConfig):
        return SimplePostgresContext(conn=create_simple_postgres_connection(config))
