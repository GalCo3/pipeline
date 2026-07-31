import logging
from abc import ABC
from typing import Any

from confluent_kafka import KafkaError, Message, Producer

from ...config_models.kafka import BaseProducerConfig
from ...exceptions import KafkaDeliveryError
from ...factories.producer import create_kafka_producer
from ...utils import dict_to_kafka_header

logger = logging.getLogger(__name__)


class BaseProducerHandler(ABC):
    config: BaseProducerConfig
    kafka_producer: Producer

    def __init__(self, config: BaseProducerConfig, is_using_schemas: bool = False):
        self.config = config

        if not hasattr(self, "kafka_producer"):
            self.kafka_producer = create_kafka_producer(config, is_using_schemas)

    @staticmethod
    def _on_delivery(error: KafkaError | None, msg: Message, is_dlq: bool) -> None:
        """Kafka produce callback - if produce failed for dlq, a log will be written,
        else, an error will be raised"""
        if error:
            if is_dlq:
                logger.error(
                    msg="Failed to deliver message",
                    extra={"target_topic": msg.topic(), "error": str(error)},
                )
            else:
                raise KafkaDeliveryError(error)

    def produce_message(
        self,
        topic: str,
        key: str,
        value: Any,
        headers: dict,
        is_dlq: bool = False,
        partition: int = -1,
        subject_name: str | None = None,
    ) -> None:
        """
        Produce a message to a Kafka topic.

        :param topic: The topic to produce the message to.
        :param key: The key of the message.
        :param value: The value of the message.
        :param headers: The headers of the message as a dictionary.
        :param subject_name: The subject name for schema registry if enabled.
        :param is_dlq: Whether to produce the message to a DLQ.
        :param partition: The partition to produce the message.
        """
        self.kafka_producer.produce(
            topic=topic,
            key=key,
            value=value,
            headers=dict_to_kafka_header(headers),
            on_delivery=lambda err, msg: self._on_delivery(err, msg, is_dlq=is_dlq),
            partition=partition,
        )

        self.kafka_producer.poll(0)

    def flush(self) -> None:
        self.kafka_producer.flush(self.config.flush_timeout)
