import logging

from confluent_kafka.admin import AdminClient

from ..config_models.kafka import BaseAdminConfig

logger = logging.getLogger(__name__)


def create_kafka_admin_client(config: BaseAdminConfig) -> AdminClient:
    """
    Create a Kafka admin client with the specified configuration.

    :param config: A `BaseAdminConfig` object containing all the necessary
        Kafka admin client settings.

    :return: An `AdminClient` object configured with the specified settings.
    """
    admin_client = AdminClient(
        {
            "bootstrap.servers": config.bootstrap_servers,
            **config.get_settings(),
        }
    )

    logger.info(
        msg="Created Kafka admin client successfully",
        extra={**config.__dict__},
    )

    return admin_client
