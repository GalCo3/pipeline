import json
import logging

from confluent_kafka import Producer, SerializingProducer
from confluent_kafka.serialization import StringSerializer

from ..config_models.kafka import BaseProducerConfig

logger = logging.getLogger(__name__)


def create_kafka_producer(
    config: BaseProducerConfig, is_using_schemas: bool = False
) -> Producer | SerializingProducer:
    """
    Create a Kafka producer with the specified configuration.

    :param config: Configuration object containing the necessary settings for
        the Kafka producer.
    :param is_using_schemas: Whether to create a producer that allows schemas
        serialization or not

    :return: A SerializingProducer object configured with the specified settings.
    """

    def json_value_serializer(obj, ctx):
        return json.dumps(obj).encode("utf-8")

    producer_config = {
        "bootstrap.servers": config.bootstrap_servers,
        **config.get_settings(),
        "retry.backoff.ms": config.retry_backoff_ms,
        "retry.backoff.max.ms": config.retry_backoff_max_ms,
        "message.max.bytes": config.message_max_bytes,
        "retries": config.retries,
    }

    if is_using_schemas:
        producer = Producer(producer_config)
    else:
        producer = SerializingProducer(
            {
                **producer_config,
                "key.serializer": StringSerializer("utf-8"),
                "value.serializer": json_value_serializer,
            }
        )

    logger.info(
        msg=(f"Created {'avro' if is_using_schemas else 'regular'} Kafka producer successfully"),
        extra={**config.__dict__},
    )

    return producer
