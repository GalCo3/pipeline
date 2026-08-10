import traceback
from datetime import UTC, datetime
from typing import cast

from confluent_kafka import Message
from pydantic import BaseModel

from hermes.connections import BaseMongoHandler
from hermes.observability import get_logger

logger = get_logger(__name__)


class DLSRecord(BaseModel):
    original_message: dict
    source_topic: str
    partition: int
    offset: int
    error: str
    error_stack: str
    failed_at: datetime


def send_to_dls(
    dls_handler: BaseMongoHandler,
    message: Message,
    error: BaseException | str | None,
    database: str,
    collection: str,
) -> None:
    error_stack = (
        "".join(traceback.format_exception(error)) if isinstance(error, BaseException) else ""
    )

    record = DLSRecord(
        # DeserializingConsumer hands back the decoded payload, not raw bytes.
        original_message=cast("dict", message.value()),
        source_topic=cast("str", message.topic()),
        partition=cast("int", message.partition()),
        offset=cast("int", message.offset()),
        error=str(error),
        error_stack=error_stack,
        failed_at=datetime.now(UTC),
    )

    dls_handler.insert_one(database, collection, record.model_dump())
    logger.info("Message sent to dead letter store", error=str(error))
