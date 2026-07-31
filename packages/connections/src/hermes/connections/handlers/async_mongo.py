import logging

from pymongo import AsyncMongoClient

from ..config_models.mongo import BaseMongoConfig
from ..factories.mongo import create_async_mongo_clients
from ..models import SiteResponse
from ..utils import execute_on_client_async

logger = logging.getLogger(__name__)


class BaseAsyncMongoHandler:
    local_client: AsyncMongoClient
    remote_client: AsyncMongoClient | None = None

    def __init__(self, config: BaseMongoConfig):
        if not hasattr(self, "local_client"):
            self.local_client, self.remote_client = create_async_mongo_clients(config)

    def _local_collection(self, database: str, collection: str):
        return self.local_client[database][collection]

    def _remote_collection(self, database: str, collection: str):
        assert self.remote_client is not None
        return self.remote_client[database][collection]

    async def find_one(
        self,
        database: str,
        collection: str,
        query: dict,
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        local_response: SiteResponse = await execute_on_client_async(
            self._local_collection(database, collection).find_one,
            query,
            *args,
            **kwargs,
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = await execute_on_client_async(
                self._remote_collection(database, collection).find_one,
                query,
                *args,
                **kwargs,
            )

        return local_response, remote_response

    async def find(
        self,
        database: str,
        collection: str,
        query: dict,
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        local_coll = self._local_collection(database, collection)

        async def _find_local():
            return await local_coll.find(query, *args, **kwargs).to_list(None)

        local_response: SiteResponse = await execute_on_client_async(_find_local)

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_coll = self._remote_collection(database, collection)

            async def _find_remote():
                return await remote_coll.find(query, *args, **kwargs).to_list(None)

            remote_response = await execute_on_client_async(_find_remote)

        return local_response, remote_response

    async def insert_one(
        self,
        database: str,
        collection: str,
        document: dict,
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        local_response: SiteResponse = await execute_on_client_async(
            self._local_collection(database, collection).insert_one,
            document,
            *args,
            **kwargs,
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = await execute_on_client_async(
                self._remote_collection(database, collection).insert_one,
                document,
                *args,
                **kwargs,
            )

        return local_response, remote_response

    async def insert_many(
        self,
        database: str,
        collection: str,
        documents: list[dict],
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        local_response: SiteResponse = await execute_on_client_async(
            self._local_collection(database, collection).insert_many,
            documents,
            *args,
            **kwargs,
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = await execute_on_client_async(
                self._remote_collection(database, collection).insert_many,
                documents,
                *args,
                **kwargs,
            )

        return local_response, remote_response

    async def update_one(
        self,
        database: str,
        collection: str,
        query: dict,
        update: dict,
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        local_response: SiteResponse = await execute_on_client_async(
            self._local_collection(database, collection).update_one,
            query,
            update,
            *args,
            **kwargs,
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = await execute_on_client_async(
                self._remote_collection(database, collection).update_one,
                query,
                update,
                *args,
                **kwargs,
            )

        return local_response, remote_response

    async def update_many(
        self,
        database: str,
        collection: str,
        query: dict,
        update: dict,
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        local_response: SiteResponse = await execute_on_client_async(
            self._local_collection(database, collection).update_many,
            query,
            update,
            *args,
            **kwargs,
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = await execute_on_client_async(
                self._remote_collection(database, collection).update_many,
                query,
                update,
                *args,
                **kwargs,
            )

        return local_response, remote_response

    async def delete_one(
        self,
        database: str,
        collection: str,
        query: dict,
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        local_response: SiteResponse = await execute_on_client_async(
            self._local_collection(database, collection).delete_one,
            query,
            *args,
            **kwargs,
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = await execute_on_client_async(
                self._remote_collection(database, collection).delete_one,
                query,
                *args,
                **kwargs,
            )

        return local_response, remote_response

    async def delete_many(
        self,
        database: str,
        collection: str,
        query: dict,
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        local_response: SiteResponse = await execute_on_client_async(
            self._local_collection(database, collection).delete_many,
            query,
            *args,
            **kwargs,
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = await execute_on_client_async(
                self._remote_collection(database, collection).delete_many,
                query,
                *args,
                **kwargs,
            )

        return local_response, remote_response

    async def close(self):
        if self.remote_client:
            await self.remote_client.close()
        if self.local_client:
            await self.local_client.close()
