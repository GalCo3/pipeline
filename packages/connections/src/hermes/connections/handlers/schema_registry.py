import json
import logging
from typing import Any

from confluent_kafka.schema_registry import (
    RegisteredSchema,
    Schema,
    SchemaRegistryClient,
    record_subject_name_strategy,
)
from confluent_kafka.schema_registry.avro import AvroSerializer

from ..config_models.kafka import BaseSchemaRegistryConfig
from ..factories.schema_registry import (
    create_kafka_schema_registry_client,
)

logger = logging.getLogger(__name__)


class BaseSchemaRegistryHandler:
    sr: SchemaRegistryClient
    serializers_cache: dict[str, AvroSerializer]

    def __init__(self, config: BaseSchemaRegistryConfig):
        if not hasattr(self, "sr"):
            self.sr = create_kafka_schema_registry_client(config)
        if not hasattr(self, "serializers_cache"):
            self.serializers_cache = {}

    def test_compatibility(self, subject_name: str, schema: Schema | dict[str, Any] | str) -> bool:
        if isinstance(schema, dict):
            schema = Schema(json.dumps(schema), schema_type="AVRO")
        elif isinstance(schema, str):
            schema = Schema(schema, schema_type="AVRO")
        return self.sr.test_compatibility(subject_name, schema, version="latest")

    def register_schema(self, subject_name: str, schema: Schema | dict[str, Any] | str) -> int:
        if isinstance(schema, dict):
            schema = Schema(json.dumps(schema), schema_type="AVRO")
        elif isinstance(schema, str):
            schema = Schema(schema, schema_type="AVRO")
        return self.sr.register_schema(subject_name, schema, normalize_schemas=False)

    def set_compatibility(self, subject_name: str, level: str) -> str:
        return self.sr.set_compatibility(subject_name, level)

    def get_serializer(self, subject_name: str) -> AvroSerializer:
        if serializer := self.serializers_cache.get(subject_name):
            return serializer

        logger.info(
            msg="Loading schema from Schema Registry",
            extra={
                "subject_name": subject_name,
            },
        )
        schema_meta = self.get_latest_version(subject_name)
        logger.info(
            msg="Schema loaded",
            extra={
                "schema_version": schema_meta.version,
                "schema_id": schema_meta.schema_id,
            },
        )

        value_serializer = AvroSerializer(
            schema_registry_client=self.sr,
            schema_str=schema_meta.schema.schema_str,
            conf={
                "auto.register.schemas": False,
                "use.latest.version": False,
                "subject.name.strategy": record_subject_name_strategy,
            },
        )

        self.serializers_cache[subject_name] = value_serializer

        return value_serializer

    def get_latest_version(self, subject: str) -> RegisteredSchema:
        return self.sr.get_latest_version(subject)

    def get_versions(self, subject: str) -> list[int]:
        return self.sr.get_versions(subject)

    def delete_subject(self, subject: str) -> None:
        self.sr.delete_subject(subject)

    def delete_version(self, subject: str, version: int) -> None:
        self.sr.delete_version(subject, version)
