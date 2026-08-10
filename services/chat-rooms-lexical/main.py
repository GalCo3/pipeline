from models import ChatRoomMessage
from settings import get_settings

from hermes.connections import (
    BaseConsumerHandler,
    BaseElasticHandler,
    BaseMongoHandler,
)
from hermes.observability import (
    TelemetryCounter,
    TelemetryHistogram,
    get_logger,
    init_observability,
    kafka_context,
)
from hermes.utils import send_to_dls, site_error, with_indexed_at

init_observability(service_name="chat-rooms-lexical")
logger = get_logger(__name__)
messages_processed = TelemetryCounter(
    "chat_rooms_lexical_messages_processed_total", allowed_labels=["status"]
)
messages_sent_to_dls = TelemetryCounter("chat_rooms_lexical_messages_dls_total")
message_duration = TelemetryHistogram(
    "chat_rooms_lexical_message_duration", unit="s", allowed_labels=["status"]
)


def main():
    settings = get_settings()
    consumer_handler = BaseConsumerHandler(settings.consumer_config)
    elastic_handler = BaseElasticHandler(settings.elastic_config)
    dls_handler = BaseMongoHandler(settings.mongo_config)

    for message in consumer_handler.start_consuming():
        try:
            with kafka_context(message, name="process_chat_room_message"):
                chat_room = ChatRoomMessage.model_validate(message.value())
                logger.info("Processing chat room message", doc_id=chat_room.id)

                with message_duration.time(labels={"status": "success"}):
                    local_response, remote_response = elastic_handler.index(
                        settings.index_name,
                        chat_room.id,
                        with_indexed_at(chat_room.model_dump(mode="json")),
                        is_multisite=True,
                    )
                    site_error(
                        local_response,
                        remote_response,
                        f"Failed to index chat-rooms-lexical document {chat_room.id}",
                    )
                logger.info("Successfully indexed chat room document", doc_id=chat_room.id)
                messages_processed.inc(labels={"status": "success"})
        except Exception as e:
            logger.error(
                "Failed to process chat room message, sending to DLS",
                error=str(e),
                exc_info=True,
            )
            messages_processed.inc(labels={"status": "error"})
            messages_sent_to_dls.inc()
            send_to_dls(
                dls_handler, message, e, settings.mongo_config.database, settings.dls_collection
            )


if __name__ == "__main__":
    main()
