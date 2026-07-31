from confluent_kafka.admin import AdminClient

from ..config_models.kafka import BaseAdminConfig
from ..factories.admin import create_kafka_admin_client


class BaseAdminHandler:
    kafka_admin: AdminClient

    def __init__(self, config: BaseAdminConfig):
        if not hasattr(self, "kafka_admin"):
            self.kafka_admin = create_kafka_admin_client(config)
