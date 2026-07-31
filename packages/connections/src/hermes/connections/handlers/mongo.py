import logging

from pymongo import MongoClient

from ..config_models.mongo import BaseMongoConfig
from ..factories.mongo import create_mongo_clients
from ..models import SiteResponse
from ..utils import execute_on_client

logger = logging.getLogger(__name__)


class BaseMongoHandler:
    local_client: MongoClient
    remote_client: MongoClient | None = None

    def __init__(self, config: BaseMongoConfig):
        if not hasattr(self, "local_client"):
            self.local_client, self.remote_client = create_mongo_clients(config)

    def _local_collection(self, database: str, collection: str):
        return self.local_client[database][collection]

    def _remote_collection(self, database: str, collection: str):
        assert self.remote_client is not None
        return self.remote_client[database][collection]

    def find_one(
        self,
        database: str,
        collection: str,
        query: dict,
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Find a single document matching a query.

        :param database: The database name.
        :param collection: The collection name.
        :param query: The filter query.
        :param is_multisite: Whether to execute in both local and remote sites.
        :return: Tuple of `SiteResponse` objects for local and remote clients.
        """
        local_response: SiteResponse = execute_on_client(
            self._local_collection(database, collection).find_one,
            query,
            *args,
            **kwargs,
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                self._remote_collection(database, collection).find_one,
                query,
                *args,
                **kwargs,
            )

        return local_response, remote_response

    def find(
        self,
        database: str,
        collection: str,
        query: dict,
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Find all documents matching a query.

        :param database: The database name.
        :param collection: The collection name.
        :param query: The filter query.
        :param is_multisite: Whether to execute in both local and remote sites.
        :return: Tuple of `SiteResponse` objects for local and remote clients.
        """
        local_response: SiteResponse = execute_on_client(
            lambda: list(self._local_collection(database, collection).find(query, *args, **kwargs))
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                lambda: list(
                    self._remote_collection(database, collection).find(query, *args, **kwargs)
                )
            )

        return local_response, remote_response

    def insert_one(
        self,
        database: str,
        collection: str,
        document: dict,
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Insert a single document.

        :param database: The database name.
        :param collection: The collection name.
        :param document: The document to insert.
        :param is_multisite: Whether to execute in both local and remote sites.
        :return: Tuple of `SiteResponse` objects for local and remote clients.
        """
        local_response: SiteResponse = execute_on_client(
            self._local_collection(database, collection).insert_one,
            document,
            *args,
            **kwargs,
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                self._remote_collection(database, collection).insert_one,
                document,
                *args,
                **kwargs,
            )

        return local_response, remote_response

    def insert_many(
        self,
        database: str,
        collection: str,
        documents: list[dict],
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Insert multiple documents.

        :param database: The database name.
        :param collection: The collection name.
        :param documents: The documents to insert.
        :param is_multisite: Whether to execute in both local and remote sites.
        :return: Tuple of `SiteResponse` objects for local and remote clients.
        """
        local_response: SiteResponse = execute_on_client(
            self._local_collection(database, collection).insert_many,
            documents,
            *args,
            **kwargs,
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                self._remote_collection(database, collection).insert_many,
                documents,
                *args,
                **kwargs,
            )

        return local_response, remote_response

    def update_one(
        self,
        database: str,
        collection: str,
        query: dict,
        update: dict,
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Update a single document matching a query.

        :param database: The database name.
        :param collection: The collection name.
        :param query: The filter query.
        :param update: The update operations.
        :param is_multisite: Whether to execute in both local and remote sites.
        :return: Tuple of `SiteResponse` objects for local and remote clients.
        """
        local_response: SiteResponse = execute_on_client(
            self._local_collection(database, collection).update_one,
            query,
            update,
            *args,
            **kwargs,
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                self._remote_collection(database, collection).update_one,
                query,
                update,
                *args,
                **kwargs,
            )

        return local_response, remote_response

    def update_many(
        self,
        database: str,
        collection: str,
        query: dict,
        update: dict,
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Update all documents matching a query.

        :param database: The database name.
        :param collection: The collection name.
        :param query: The filter query.
        :param update: The update operations.
        :param is_multisite: Whether to execute in both local and remote sites.
        :return: Tuple of `SiteResponse` objects for local and remote clients.
        """
        local_response: SiteResponse = execute_on_client(
            self._local_collection(database, collection).update_many,
            query,
            update,
            *args,
            **kwargs,
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                self._remote_collection(database, collection).update_many,
                query,
                update,
                *args,
                **kwargs,
            )

        return local_response, remote_response

    def delete_one(
        self,
        database: str,
        collection: str,
        query: dict,
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Delete a single document matching a query.

        :param database: The database name.
        :param collection: The collection name.
        :param query: The filter query.
        :param is_multisite: Whether to execute in both local and remote sites.
        :return: Tuple of `SiteResponse` objects for local and remote clients.
        """
        local_response: SiteResponse = execute_on_client(
            self._local_collection(database, collection).delete_one,
            query,
            *args,
            **kwargs,
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                self._remote_collection(database, collection).delete_one,
                query,
                *args,
                **kwargs,
            )

        return local_response, remote_response

    def delete_many(
        self,
        database: str,
        collection: str,
        query: dict,
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Delete all documents matching a query.

        :param database: The database name.
        :param collection: The collection name.
        :param query: The filter query.
        :param is_multisite: Whether to execute in both local and remote sites.
        :return: Tuple of `SiteResponse` objects for local and remote clients.
        """
        local_response: SiteResponse = execute_on_client(
            self._local_collection(database, collection).delete_many,
            query,
            *args,
            **kwargs,
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                self._remote_collection(database, collection).delete_many,
                query,
                *args,
                **kwargs,
            )

        return local_response, remote_response

    def close(self):
        if self.remote_client:
            self.remote_client.close()
        if self.local_client:
            self.local_client.close()
