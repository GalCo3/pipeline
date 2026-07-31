from confluent_kafka import SerializingProducer

from ...config_models.kafka import BaseProducerConfig
from ..kafka_producers.base_producer import (
    BaseProducerHandler,
)


class BasePlainProducerHandler(BaseProducerHandler):
    kafka_producer: SerializingProducer

    def __init__(self, config: BaseProducerConfig):
        super().__init__(config, is_using_schemas=False)
