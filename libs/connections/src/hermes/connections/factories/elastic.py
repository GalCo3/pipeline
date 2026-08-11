import logging

from elasticsearch import Elasticsearch

from ..config_models.elastic import (
    BaseElasticBasicConfig,
    BaseElasticCertConfig,
    BaseElasticJWTConfig,
)

logger = logging.getLogger(__name__)


def _create_raw_client(
    elastic_config: (BaseElasticCertConfig | BaseElasticJWTConfig | BaseElasticBasicConfig),
    is_local_client: bool,
) -> Elasticsearch:
    config_options: dict = {
        "hosts": elastic_config.local_host if is_local_client else elastic_config.remote_host,
        "ssl_show_warn": False,
        "max_retries": elastic_config.max_retries,
        "request_timeout": elastic_config.request_timeout,
        "retry_on_timeout": True,
    }

    match elastic_config:
        case BaseElasticCertConfig():
            auth = elastic_config.local_auth if is_local_client else elastic_config.remote_auth
            if auth is None:
                raise ValueError("remote_auth must be set for cert-based remote connections")
            config_options["ca_certs"] = auth.ca_path
            config_options["client_cert"] = auth.cert_path
            config_options["client_key"] = auth.key_path
            config_options["verify_certs"] = True
        case BaseElasticJWTConfig():
            config_options["bearer_auth"] = elastic_config.jwt
            config_options["verify_certs"] = False
        case BaseElasticBasicConfig():
            config_options["basic_auth"] = (
                elastic_config.username,
                elastic_config.password.get_secret_value(),
            )

    return Elasticsearch(**config_options)


def create_elastic_clients(
    elastic_config: (BaseElasticCertConfig | BaseElasticJWTConfig | BaseElasticBasicConfig),
) -> tuple[Elasticsearch, Elasticsearch | None]:
    """
    Create local and remote (if exists) Elasticsearch clients.

    :param elastic_config: Configuration object containing the necessary settings
    for the Elasticsearch clients.

    :return: A tuple containing the local Elasticsearch client
    and the remote Elasticsearch client (if it exists)
    """
    local_client: Elasticsearch = _create_raw_client(elastic_config, is_local_client=True)
    remote_client: Elasticsearch | None = None

    logger.info(msg="Created local elasticsearch client", extra=elastic_config.__dict__)

    if elastic_config.remote_host is not None:
        remote_client = _create_raw_client(elastic_config, is_local_client=False)

        logger.info(msg="Created remote elasticsearch client", extra=elastic_config.__dict__)

    return local_client, remote_client
