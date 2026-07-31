import logging

from confluent_kafka.schema_registry import SchemaRegistryClient

from ..config_models.kafka import BaseSchemaRegistryConfig

logger = logging.getLogger(__name__)


def create_kafka_schema_registry_client(
    config: BaseSchemaRegistryConfig,
) -> SchemaRegistryClient:
    client_config: dict[str, str] = {"url": config.url}

    if config.access_key is not None and config.secret_key is not None:
        client_config["basic.auth.user.info"] = f"{config.access_key}:{config.secret_key}"

    if config.ssl_ca_location is not None:
        client_config["ssl.ca.location"] = str(config.ssl_ca_location)

    client = SchemaRegistryClient(client_config)

    logger.info(
        msg="Created Kafka schema registry client successfully",
        extra={**config.__dict__},
    )

    return client
