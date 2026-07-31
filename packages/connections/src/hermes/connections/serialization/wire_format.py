import io
import json
import struct

import fastavro

from ..handlers.schema_registry import BaseSchemaRegistryHandler

_MAGIC = b"\x00"


class SchemaFetchError(Exception):
    """SR unreachable or the subject has no registered schema."""


class PayloadInvalid(Exception):
    """Payload does not conform to the schema. Carries field-level messages."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def _frame(schema_id: int, body: bytes) -> bytes:
    return _MAGIC + struct.pack(">I", schema_id) + body


def _avro_body(schema_str: str, payload: object) -> bytes:
    parsed = fastavro.parse_schema(json.loads(schema_str))
    buf = io.BytesIO()
    try:
        fastavro.schemaless_writer(buf, parsed, payload)
    except Exception as exc:
        raise PayloadInvalid([str(exc)]) from exc
    return buf.getvalue()


def _json_body(schema_str: str, payload: object) -> bytes:
    errors = _json_errors(schema_str, payload)
    if errors:
        raise PayloadInvalid(errors)
    return json.dumps(payload).encode("utf-8")


def _json_errors(schema_str: str, payload: object) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return []
    try:
        jsonschema.validate(payload, json.loads(schema_str))
    except jsonschema.ValidationError as exc:
        return [exc.message]
    return []


class WireFormatSerializer:
    """Confluent wire-format serializer keyed by an explicit schema subject.

    Frames ``magic 0 + schema id + body`` off the subject's latest registered
    schema, so the SR client's subject-name strategy never applies (subjects
    are resolved by the caller, not derived from the record name). Supports
    AVRO and JSON schema types.
    """

    def __init__(self, sr_handler: BaseSchemaRegistryHandler):
        self._sr = sr_handler

    def _fetch(self, subject: str) -> tuple[int, str, str]:
        try:
            registered = self._sr.get_latest_version(subject)
        except Exception as exc:
            raise SchemaFetchError(f"schema subject '{subject}': {exc}") from exc
        schema = registered.schema
        return registered.schema_id, (schema.schema_type or "AVRO"), schema.schema_str

    def serialize(self, subject: str, payload: object) -> bytes:
        schema_id, schema_type, schema_str = self._fetch(subject)
        if schema_type == "AVRO":
            return _frame(schema_id, _avro_body(schema_str, payload))
        if schema_type == "JSON":
            return _frame(schema_id, _json_body(schema_str, payload))
        raise SchemaFetchError(f"unsupported schema type '{schema_type}' for subject '{subject}'")

    def validate(self, subject: str, payload: object) -> list[str]:
        """Dry run: ``[]`` if the payload fits the schema, else field messages.

        Propagates :class:`SchemaFetchError` (can't validate without a schema).
        """
        try:
            self.serialize(subject, payload)
        except PayloadInvalid as exc:
            return exc.errors
        return []
