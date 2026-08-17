from hermes.connections.config_models.elastic import (
    BaseElasticBasicConfig,
    BaseElasticCertConfig,
    BaseElasticConfig,
    BaseElasticJWTConfig,
)
from hermes.connections.config_models.kafka import (
    BaseAdminConfig,
    BaseConsumerConfig,
    BaseKafkaSecurityConfig,
    BaseProducerConfig,
    BaseSchemaRegistryConfig,
)
from hermes.connections.config_models.mongo import BaseMongoConfig, BasicAuth, MongoSSL, X509Auth
from hermes.connections.config_models.postgres import BasePostgresConfig
from hermes.connections.config_models.s3 import BaseS3Config, BaseS3SiteConfig
from hermes.connections.config_models.ssl import SSL
from hermes.connections.config_models.triton import BaseTritonConfig, BaseTritonSiteConfig
from hermes.connections.contexts.postgres import (
    PostgresContext,
    SimplePostgresContext,
    handle_postgres_exceptions,
)
from hermes.connections.exceptions import (
    KafkaDeliveryError,
    ProducerSchemaError,
    S3Error,
    SchemaExhaustedError,
    SchemaPermanentError,
)
from hermes.connections.factories.admin import create_kafka_admin_client
from hermes.connections.factories.consumer import create_kafka_consumer
from hermes.connections.factories.elastic import create_elastic_clients
from hermes.connections.factories.mongo import create_async_mongo_clients, create_mongo_clients
from hermes.connections.factories.postgres import (
    create_postgres_connection_pool,
    create_simple_postgres_connection,
)
from hermes.connections.factories.producer import create_kafka_producer
from hermes.connections.factories.s3 import create_s3_clients, create_s3_raw_client
from hermes.connections.factories.schema_registry import create_kafka_schema_registry_client
from hermes.connections.factories.triton import create_triton_clients
from hermes.connections.handlers.admin import BaseAdminHandler
from hermes.connections.handlers.async_mongo import BaseAsyncMongoHandler
from hermes.connections.handlers.consumer import BaseConsumerHandler
from hermes.connections.handlers.elastic import BaseElasticHandler
from hermes.connections.handlers.kafka_producers.avro_producer import BaseAvroProducerHandler
from hermes.connections.handlers.kafka_producers.base_producer import BaseProducerHandler
from hermes.connections.handlers.kafka_producers.plain_producer import BasePlainProducerHandler
from hermes.connections.handlers.mongo import BaseMongoHandler
from hermes.connections.handlers.s3 import BaseS3Handler
from hermes.connections.handlers.schema_registry import BaseSchemaRegistryHandler
from hermes.connections.handlers.triton import BaseTritonHandler
from hermes.connections.models import SiteResponse
from hermes.connections.serialization.wire_format import (
    PayloadInvalid,
    SchemaFetchError,
    WireFormatSerializer,
)
from hermes.connections.utils import (
    dict_to_kafka_header,
    execute_on_client,
    is_produce_error_retryable,
    kafka_header_to_dict,
    map_assignment_by_topics,
    retry,
    retry_on_conflict,
)

__all__ = [
    "SSL",
    "BaseAdminConfig",
    "BaseAdminHandler",
    "BaseAsyncMongoHandler",
    "BaseAvroProducerHandler",
    "BaseConsumerConfig",
    "BaseConsumerHandler",
    "BaseElasticBasicConfig",
    "BaseElasticCertConfig",
    "BaseElasticConfig",
    "BaseElasticHandler",
    "BaseElasticJWTConfig",
    "BaseKafkaSecurityConfig",
    "BaseMongoConfig",
    "BaseMongoHandler",
    "BasePlainProducerHandler",
    "BasePostgresConfig",
    "BaseProducerConfig",
    "BaseProducerHandler",
    "BaseS3Config",
    "BaseS3Handler",
    "BaseS3SiteConfig",
    "BaseSchemaRegistryConfig",
    "BaseSchemaRegistryHandler",
    "BaseTritonConfig",
    "BaseTritonHandler",
    "BaseTritonSiteConfig",
    "BasicAuth",
    "KafkaDeliveryError",
    "MongoSSL",
    "PayloadInvalid",
    "PostgresContext",
    "ProducerSchemaError",
    "S3Error",
    "SchemaExhaustedError",
    "SchemaFetchError",
    "SchemaPermanentError",
    "SimplePostgresContext",
    "SiteResponse",
    "WireFormatSerializer",
    "X509Auth",
    "create_async_mongo_clients",
    "create_elastic_clients",
    "create_kafka_admin_client",
    "create_kafka_consumer",
    "create_kafka_producer",
    "create_kafka_schema_registry_client",
    "create_mongo_clients",
    "create_postgres_connection_pool",
    "create_s3_clients",
    "create_s3_raw_client",
    "create_simple_postgres_connection",
    "create_triton_clients",
    "dict_to_kafka_header",
    "execute_on_client",
    "handle_postgres_exceptions",
    "is_produce_error_retryable",
    "kafka_header_to_dict",
    "map_assignment_by_topics",
    "retry",
    "retry_on_conflict",
]
