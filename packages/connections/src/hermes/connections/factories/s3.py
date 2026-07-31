import logging

import boto3
from botocore.client import BaseClient
from botocore.config import Config

from ..config_models.s3 import BaseS3Config

logger = logging.getLogger(__name__)


def create_s3_raw_client(s3_site_config):
    return boto3.client(
        "s3",
        aws_access_key_id=s3_site_config.access_key,
        aws_secret_access_key=s3_site_config.secret_key,
        endpoint_url=s3_site_config.endpoint,
        verify=False,
        config=Config(read_timeout=s3_site_config.read_timeout_seconds),
    )


def create_s3_clients(config: BaseS3Config) -> tuple[BaseClient, BaseClient | None]:
    """
    Create local and remote (if exists) S3 clients.

    :param config: Configuration object containing the necessary settings for
        the S3 clients.

    :return: A tuple containing the local S3 client and the remote S3 client
        (if exists), both of type `BaseClient`.
    """
    local_client: BaseClient = create_s3_raw_client(config.local_site)
    remote_client: BaseClient | None = None

    logger.info(msg="Created local s3 client", extra=config.__dict__)

    if config.remote_site is not None:
        remote_client = create_s3_raw_client(config.remote_site)

        logger.info(msg="Created remote s3 client", extra=config.__dict__)

    return local_client, remote_client
