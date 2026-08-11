import logging
from typing import cast

import tenacity
from confluent_kafka.schema_registry import SchemaRegistryError
from confluent_kafka.serialization import (
    MessageField,
    SerializationContext,
    SerializationError,
    StringSerializer,
)

from ...config_models.kafka import (
    BaseProducerConfig,
    BaseSchemaRegistryConfig,
)
from ...exceptions import SchemaExhaustedError, SchemaPermanentError
from ...handlers.kafka_producers.base_producer import (
    BaseProducerHandler,
)
from ...utils import is_produce_error_retryable
from ..schema_registry import BaseSchemaRegistryHandler

logger = logging.getLogger(__name__)


class BaseAvroProducerHandler(BaseProducerHandler):
    schema_registry_handler: BaseSchemaRegistryHandler
    key_serializer: StringSerializer

    def __init__(self, config: BaseProducerConfig, sr_config: BaseSchemaRegistryConfig):
        super().__init__(config, is_using_schemas=True)

        if not hasattr(self, "schema_registry_handler"):
            self.key_serializer: StringSerializer = StringSerializer("utf-8")
            self.schema_registry_handler = BaseSchemaRegistryHandler(sr_config)

    def produce_message(
        self,
        topic: str,
        key: str,
        value: dict,
        headers: dict,
        is_dlq: bool = False,
        partition: int = -1,
        subject_name: str | None = None,
        retry_multiplier: int = 2,
    ) -> None:
        if subject_name is None:
            raise ValueError("subject_name is required for BaseAvroProducerHandler")

        @tenacity.retry(
            wait=tenacity.wait_exponential(
                multiplier=retry_multiplier,
                min=self.config.retry_backoff_ms,
                max=self.config.retry_backoff_max_ms,
            ),
            stop=tenacity.stop_after_attempt(self.config.retries),
            reraise=True,
            retry=tenacity.retry_if_exception(is_produce_error_retryable),
            before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
        )
        def produce_with_retry() -> None:
            ctx_key = SerializationContext(topic, MessageField.KEY)
            ctx_value = SerializationContext(topic, MessageField.VALUE)

            serialized_key = self.key_serializer(key, ctx_key)

            serialized_value = self.schema_registry_handler.get_serializer(subject_name)(
                value, ctx_value
            )
            super(BaseAvroProducerHandler, self).produce_message(
                topic,
                cast(str, serialized_key),
                serialized_value,
                headers,
                is_dlq,
                partition,
            )

        try:
            produce_with_retry()
        except (SerializationError, ValueError, SchemaRegistryError) as e:
            if is_produce_error_retryable(e):
                # retries have already done and failed
                raise SchemaExhaustedError(e) from e
            raise SchemaPermanentError(e) from e
