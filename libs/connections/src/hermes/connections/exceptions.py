from confluent_kafka import KafkaError


class S3Error(Exception):
    def __init__(self, responses: dict | list[dict]):
        self.responses = responses


class KafkaDeliveryError(Exception):
    def __init__(self, error: KafkaError):
        self.error = error


class ProducerSchemaError(Exception):
    def __init__(self, error: Exception):
        self.error = error
        self.message = str(error)


class SchemaPermanentError(ProducerSchemaError):
    pass


class SchemaExhaustedError(ProducerSchemaError):
    pass
