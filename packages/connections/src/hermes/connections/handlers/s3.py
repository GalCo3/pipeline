import json
import logging
from typing import Any

from ..config_models.s3 import BaseS3Config
from ..factories.s3 import create_s3_clients
from ..models import SiteResponse
from ..utils import execute_on_client

logger = logging.getLogger(__name__)


class BaseS3Handler:
    local_client: Any
    remote_client: Any = None

    def __init__(self, config: BaseS3Config):
        if not hasattr(self, "local_client"):
            self.local_client, self.remote_client = create_s3_clients(config)

    def put_object(
        self,
        key: str,
        content: dict,
        bucket: str,
        is_multisite: bool = False,
        *args,
        **kwargs,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Save a given file in S3 and in both sites if required.

        :param key: The name of the file.
        :param content: The content of the file as a dictionary.
        :param bucket: The name of the S3 bucket.
        :param is_multisite: Whether to execute operation in both local and
            remote sites.
        :return: A tuple of `SiteResponse` objects for local and remote clients.
        """
        data = json.dumps(content).encode("utf-8")

        local_response: SiteResponse = execute_on_client(
            self.local_client.put_object,
            *args,
            Body=data,
            Bucket=bucket,
            Key=key,
            ContentType="application/json",
            **kwargs,
        )

        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                self.remote_client.put_object,
                *args,
                Body=data,
                Bucket=bucket,
                Key=key,
                ContentType="application/json",
                **kwargs,
            )

        return local_response, remote_response

    def get_file(
        self, key: str, bucket: str, is_multisite: bool = False, *args, **kwargs
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Get a file from S3.

        :param key: The name of the file.
        :param bucket: The name of the S3 bucket.
        :param is_multisite: Whether to execute operation in both local and
            remote sites.
        :return: A tuple of `SiteResponse` objects for local and remote clients.
        """
        local_response: SiteResponse = execute_on_client(
            self.local_client.get_object, *args, Bucket=bucket, Key=key, **kwargs
        )
        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                self.remote_client.get_object, *args, Bucket=bucket, Key=key, **kwargs
            )

        return local_response, remote_response

    def delete_file(
        self, key: str, bucket: str, is_multisite: bool = False, *args, **kwargs
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        Delete a file from S3.

        :param key: The name of the file.
        :param bucket: The name of the S3 bucket.
        :param is_multisite: Whether to execute operation in both local and
            remote sites.
        :return: A tuple of `SiteResponse` objects for local and remote clients.
        """
        local_response: SiteResponse = execute_on_client(
            self.local_client.delete_object, *args, Bucket=bucket, Key=key, **kwargs
        )
        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                self.remote_client.delete_object,
                *args,
                Bucket=bucket,
                Key=key,
                **kwargs,
            )

        return local_response, remote_response

    def list_files_by_prefix(
        self, prefix: str, bucket: str, is_multisite: bool = False, *args, **kwargs
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """
        List files from S3 beginning by a given prefix.

        :param prefix: The prefix of the file names.
        :param bucket: The name of the S3 bucket.
        :param is_multisite: Whether to execute operation in both local and
            remote sites.
        :return: A tuple of `SiteResponse` objects for local and remote clients.
        """
        local_response: SiteResponse = execute_on_client(
            self.local_client.list_objects,
            *args,
            Bucket=bucket,
            Prefix=prefix,
            **kwargs,
        )
        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_response = execute_on_client(
                self.remote_client.list_objects,
                *args,
                Bucket=bucket,
                Prefix=prefix,
                **kwargs,
            )

        return local_response, remote_response

    def close(self):
        if self.remote_client:
            self.remote_client.close()
        if self.local_client:
            self.local_client.close()
