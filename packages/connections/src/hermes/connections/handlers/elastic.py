import logging
from collections.abc import Generator
from typing import Any

from elasticsearch import Elasticsearch, helpers

from ..config_models.elastic import (
    BaseElasticBasicConfig,
    BaseElasticCertConfig,
    BaseElasticJWTConfig,
)
from ..factories.elastic import create_elastic_clients
from ..models import SiteResponse
from ..utils import execute_on_client

logging.getLogger("elastic_transport").setLevel(logging.ERROR)


class BaseElasticHandler:
    local_client: Elasticsearch
    remote_client: Elasticsearch | None = None

    def __init__(
        self,
        config: BaseElasticCertConfig | BaseElasticJWTConfig | BaseElasticBasicConfig,
    ):
        if not hasattr(self, "local_client"):
            self.local_client, self.remote_client = create_elastic_clients(config)

    def search(
        self, index: str, query: dict, is_multisite: bool = False, *args, **kwargs
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Search an elastic index
        :param index: The index name.
        :param query: The search query.
        :param is_multisite: Whether to execute a search in multiple sites.
        :return: Tuple of `SiteResponse` objects for local and remote clients.
        """
        local_response: SiteResponse = execute_on_client(
            self.local_client.search, *args, index=index, query=query, **kwargs
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                self.remote_client.search, *args, index=index, query=query, **kwargs
            )

        return local_response, remote_response

    def scroll(
        self,
        index: str,
        query: dict,
        scroll: str = "1m",
        size: int = 10,
        *args,
        **kwargs,
    ) -> Generator[Any, None, SiteResponse]:
        """
        Scroll an index - done only in the local client.

        :param index: The index name.
        :param query: The search query.
        :param scroll: The scroll timeout.
        :return: `SiteResponse` object containing the scroll results.
        """
        local_response, _remote_response = self.search(
            index, query, *args, scroll=scroll, size=size, **kwargs
        )

        while local_response.is_success:
            yield local_response.response

            scroll_id = (
                local_response.response.get("_scroll_id")
                if isinstance(local_response.response, dict)
                else None
            )

            if not scroll_id:
                return local_response
            else:
                local_response = execute_on_client(
                    self.local_client.scroll,
                    *args,
                    scroll_id=scroll_id,
                    scroll=scroll,
                    **kwargs,
                )
        else:
            return local_response

    def search_by_id(
        self, index: str, doc_id: str, is_multisite: bool = False, *args, **kwargs
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Search an elastic index for a specific id.

        :param index: The index name.
        :param doc_id: The document ID.
        :param is_multisite: Whether to execute search in multiple sites.
        :return: Tuple of `SiteResponse` objects for local and remote clients.
        """
        local_response: SiteResponse = execute_on_client(
            self.local_client.get, *args, index=index, id=doc_id, **kwargs
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                self.remote_client.get, *args, index=index, id=doc_id, **kwargs
            )

        return local_response, remote_response

    def delete_by_id(
        self, index: str, doc_id: str, is_multisite: bool = False, *args, **kwargs
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Delete from the elastic index a specific id.

        :param index: The index name.
        :param doc_id: The document ID.
        :param is_multisite: Whether to execute delete in multiple sites.
        :return: Tuple of `SiteResponse` objects for local and remote clients.
        """
        local_response: SiteResponse = execute_on_client(
            self.local_client.delete, *args, index=index, id=doc_id, **kwargs
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                self.remote_client.delete, *args, index=index, id=doc_id, **kwargs
            )

        return local_response, remote_response

    def delete_by_query(
        self, index: str, query: dict, is_multisite: bool = False, *args, **kwargs
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Delete from elastic index by a given query.

        :param index: The index name.
        :param query: The deletion query.
        :param is_multisite: Whether to execute delete in multiple sites.
        :return: Tuple of `SiteResponse` objects for local and remote clients.
        """
        local_response: SiteResponse = execute_on_client(
            self.local_client.delete_by_query, *args, index=index, query=query, **kwargs
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                self.remote_client.delete_by_query,
                *args,
                index=index,
                query=query,
                **kwargs,
            )

        return local_response, remote_response

    def update_by_id(
        self,
        index: str,
        doc_id: str,
        body: dict,
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Update by id a file in elastic.

        :param index: The index name.
        :param doc_id: The document ID.
        :param body: The document to update.
        :param is_multisite: Whether to execute update in multiple sites.
        :return: Tuple of `SiteResponse` objects for local and remote clients.
        """
        local_response: SiteResponse = execute_on_client(
            self.local_client.update, *args, index=index, id=doc_id, body=body, **kwargs
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                self.remote_client.update,
                *args,
                index=index,
                id=doc_id,
                body=body,
                **kwargs,
            )

        return local_response, remote_response

    def update_by_query(
        self, index: str, body: dict, is_multisite: bool = False, *args, **kwargs
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Update by query docs in elastic.

        :param index: The index name.
        :param body: The update body.
        :param is_multisite: Whether to execute update in multiple sites.
        :return: Tuple of `SiteResponse` objects for local and remote clients.
        """
        local_response: SiteResponse = execute_on_client(
            self.local_client.update_by_query, *args, index=index, body=body, **kwargs
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                self.remote_client.update_by_query,
                *args,
                index=index,
                body=body,
                **kwargs,
            )

        return local_response, remote_response

    def index(
        self,
        index: str,
        doc_id: str,
        body: dict,
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Index a doc into an elastic index.

        :param index: The index name.
        :param doc_id: The document ID.
        :param body: The document to index.
        :param is_multisite: Whether to execute index in multiple sites.
        :return: Tuple of `SiteResponse` objects for local and remote clients.
        """
        local_response: SiteResponse = execute_on_client(
            self.local_client.index, *args, index=index, id=doc_id, body=body, **kwargs
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                self.remote_client.index,
                *args,
                index=index,
                id=doc_id,
                body=body,
                **kwargs,
            )

        return local_response, remote_response

    def stream_bulk(
        self, actions: list[dict], is_multisite: bool = False, *args, **kwargs
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Use streaming bulk helper to perform actions on elastic in stream

        :param actions: The actions to execute.
        :param is_multisite: Whether to execute index in multiple sites.
        :return: Tuple of `SiteResponse` objects for local and remote clients.
        """

        def bulk_func(*bulk_args, **bulk_kwargs):
            return helpers.streaming_bulk(*bulk_args, **bulk_kwargs)

        local_response: SiteResponse = execute_on_client(
            bulk_func, self.local_client, actions, *args, **kwargs
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                bulk_func, self.remote_client, actions, *args, **kwargs
            )

        return local_response, remote_response

    def close(self):
        if self.remote_client:
            self.remote_client.close()
        if self.local_client:
            self.local_client.close()

    def __client_alive(self, client: Elasticsearch | None) -> bool:
        if not client:
            return True

        try:
            health = client.cluster.health(timeout="3s")
            return health.get("status") == "green"
        except Exception:
            return False

    def is_alive(self) -> tuple[bool, bool]:
        return (
            self.__client_alive(self.local_client),
            self.__client_alive(self.remote_client),
        )

    def get_mappings(self, logical_name: str) -> dict[str, Any]:
        mappings = self.local_client.indices.get_mapping(index=logical_name)
        physical_name = next(iter(mappings.keys()))
        settings = self.local_client.indices.get_settings(index=physical_name)

        return {
            "physical_name": physical_name,
            "mappings": mappings[physical_name]["mappings"],
            "settings": settings[physical_name]["settings"]["index"],
        }

    def create_index(
        self,
        name: str,
        *,
        mappings: dict[str, Any],
        settings: dict[str, Any],
        aliases: dict[str, Any],
        is_multisite: bool = False,
    ) -> None:
        self.local_client.indices.create(
            index=name, mappings=mappings, settings=settings, aliases=aliases
        )
        if is_multisite and self.remote_client:
            self.remote_client.indices.create(
                index=name, mappings=mappings, settings=settings, aliases=aliases
            )

    def put_mapping(
        self,
        name: str,
        *,
        properties: dict[str, Any],
        runtime: dict[str, Any],
        is_multisite: bool = False,
    ) -> None:
        body: dict[str, Any] = {"properties": properties}

        if runtime:
            body["runtime"] = runtime

        self.local_client.indices.put_mapping(index=name, **body)

        if is_multisite and self.remote_client:
            self.remote_client.indices.put_mapping(index=name, **body)

    def delete_index(self, name: str, is_multisite: bool = False) -> None:
        self.local_client.indices.delete(index=name)

        if is_multisite and self.remote_client:
            self.remote_client.indices.delete(index=name)
