import logging
import pathlib
from collections.abc import Generator

from confluent_kafka import (
    DeserializingConsumer,
    Message,
)
from pydantic import PositiveFloat

from ..config_models.kafka import (
    BaseConsumerConfig,
    BaseSchemaRegistryConfig,
)
from ..factories.consumer import create_kafka_consumer
from ..utils import kafka_header_to_dict

logger = logging.getLogger(__name__)


class BaseConsumerHandler:
    kafka_consumer: DeserializingConsumer
    poll_timeout: PositiveFloat
    liveness_file_path: str | None

    def __init__(
        self,
        config: BaseConsumerConfig,
        is_multisite: bool = False,
        schema_registry_config: BaseSchemaRegistryConfig | None = None,
    ):
        self.poll_timeout = config.poll_timeout
        self.liveness_file_path = config.liveness_file_path

        if not hasattr(self, "kafka_consumer"):
            self.kafka_consumer = create_kafka_consumer(
                config, is_multisite, schema_registry_config
            )

    def _update_liveness_probe(self):
        if self.liveness_file_path:
            try:
                pathlib.Path(self.liveness_file_path).touch()
            except Exception as e:
                logger.warning(f"Failed to touch liveness probe at {self.liveness_file_path}: {e}")

    def _consume_single_message(self) -> Message | None:
        """
        Consume a single kafka message
        :return: A formatted kafka message (in json) if exists
        """
        message = self.kafka_consumer.poll(self.poll_timeout)

        self._update_liveness_probe()

        if not message:
            return None
        headers = kafka_header_to_dict(message.headers())
        if message.error():
            logger.error(
                msg="Failed to consume message",
                extra={
                    "topic": message.topic(),
                    "partition": message.partition(),
                    "offset": message.offset(),
                    "id": message.key(),
                    "error": message.error(),
                    **headers,
                },
            )

            return None
        logger.info(
            msg="Consumed message successfully",
            extra={
                "topic": message.topic(),
                "partition": message.partition(),
                "offset": message.offset(),
                "id": message.key(),
                **headers,
            },
        )

        message.set_headers(headers)
        return message

    def __consume_loop(self) -> Generator[Message]:
        """
        A loop for consuming endlessly from kafka
        """
        while True:
            message: Message | None = self._consume_single_message()
            if message is None:
                continue
            yield message

    def start_consuming(self, commit: bool = True) -> Generator[Message]:
        """
        Consumes Kafka messages while committing.
        Yields:
            Message: The next message from the Kafka consumer.
        """
        try:
            for message in self.__consume_loop():
                yield message

                if commit:
                    self.commit()
        finally:
            self.close()

    def commit(self, message: Message | None = None):
        if not message:
            self.kafka_consumer.commit()
        else:
            self.kafka_consumer.commit(message=message)

    def close(self):
        self.kafka_consumer.close()
