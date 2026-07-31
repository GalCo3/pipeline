import json
import logging

from confluent_kafka import DeserializingConsumer
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import StringDeserializer

from ..config_models.kafka import (
    BaseConsumerConfig,
    BaseSchemaRegistryConfig,
)
from ..factories.schema_registry import (
    create_kafka_schema_registry_client,
)

logger = logging.getLogger(__name__)


def create_kafka_consumer(
    config: BaseConsumerConfig,
    is_multisite: bool = False,
    schema_registry_config: BaseSchemaRegistryConfig | None = None,
) -> DeserializingConsumer:
    """
    Create a Kafka consumer with the specified configuration.

    :param config: A `BaseConsumerConfig` object containing all the necessary
        Kafka consumer settings.
    :param is_multisite: A boolean indicating whether to subscribe to a
        multisite topic pattern. Defaults to False.
    :param schema_registry_config: The configuration of the schema registry.
        It is optional.
    If not provided - a regular consumer will be created.

    :return: A `DeserializingConsumer` object configured with the specified settings.
    """
    schema_registry_deserializer: AvroDeserializer | None = None

    def json_value_deserializer(value: bytes | None, ctx):
        try:
            if value is None:
                logging.error("Kafka message can't be none!")
                return None

            loaded_value = json.loads(value.decode("utf-8"))

            if not isinstance(loaded_value, (dict, list)):
                logging.error(
                    msg=(
                        "Failed to deserialize message value and convert to json, "
                        "message must be of type dict or list!"
                    ),
                    extra={"value": value},
                )
                return None

            return loaded_value
        except json.JSONDecodeError:
            logging.error(
                msg="Failed to deserialize message value and convert to json",
                extra={"value": value},
            )
            return None

    if schema_registry_config:
        schema_registry_client = create_kafka_schema_registry_client(schema_registry_config)

        schema_registry_deserializer = AvroDeserializer(schema_registry_client)

    consumer_config = {
        "bootstrap.servers": config.bootstrap_servers,
        **config.get_settings(),
        "group.id": config.group_id,
        "auto.offset.reset": config.auto_offset_reset,
        "enable.auto.commit": config.enable_auto_commit,
        "fetch.max.bytes": config.fetch_max_bytes,
        "session.timeout.ms": config.session_timeout_ms,
        "max.poll.interval.ms": config.max_poll_interval_ms,
        "key.deserializer": StringDeserializer("utf-8"),
        "value.deserializer": schema_registry_deserializer
        if schema_registry_deserializer
        else json_value_deserializer,
    }

    consumer = DeserializingConsumer(consumer_config)

    logger.info(
        msg=(
            f"Created {'avro' if schema_registry_config else 'regular'} Kafka consumer successfully"
        ),
        extra={**config.__dict__, "schema_registry_config": schema_registry_config},
    )

    consumer.subscribe(
        [rf"^(.+\.)?({'|'.join(config.source_topics)})$"] if is_multisite else config.source_topics
    )

    logger.info(
        msg="Kafka consumer subscribed to topics successfully",
        extra={"multisite": is_multisite, **config.__dict__},
    )

    return consumer
