from models import ChatEnrichedMessage, ChatMessage
from settings import get_settings
from utils import build_midur_ids

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

init_observability(service_name="chat-messages-lexical")
logger = get_logger(__name__)
messages_processed = TelemetryCounter(
    "chat_messages_lexical_messages_processed_total", allowed_labels=["status"]
)
messages_sent_to_dls = TelemetryCounter("chat_messages_lexical_messages_dls_total")
message_duration = TelemetryHistogram(
    "chat_messages_lexical_message_duration", unit="s", allowed_labels=["status"]
)


def main():
    settings = get_settings()
    consumer_handler = BaseConsumerHandler(settings.consumer_config)
    elastic_handler = BaseElasticHandler(settings.elastic_config)
    dls_handler = BaseMongoHandler(settings.mongo_config)

    for message in consumer_handler.start_consuming():
        try:
            with kafka_context(message, name="process_chat_message"):
                chat_message = ChatMessage.model_validate(message.value())
                logger.info("Processing chat message", doc_id=chat_message.id)

                if chat_message.t:
                    with message_duration.time(labels={"status": "deleted"}):
                        local_response, remote_response = elastic_handler.delete_by_id(
                            settings.index_name, chat_message.id, is_multisite=True
                        )
                        site_error(
                            local_response,
                            remote_response,
                            f"Failed to delete chat-messages-lexical document {chat_message.id}",
                        )
                    logger.info("Deleted chat message document", doc_id=chat_message.id)
                    messages_processed.inc(labels={"status": "deleted"})
                    continue

                with message_duration.time(labels={"status": "success"}):
                    chat_enriched_message = ChatEnrichedMessage(
                        **chat_message.model_dump(mode="json"),
                        midur_ids=build_midur_ids(chat_message),
                    )

                    local_response, remote_response = elastic_handler.index(
                        settings.index_name,
                        chat_enriched_message.id,
                        with_indexed_at(chat_enriched_message.model_dump(mode="json")),
                        is_multisite=True,
                    )
                    site_error(
                        local_response,
                        remote_response,
                        f"Failed to index chat-messages-lexical document {chat_message.id}",
                    )
                logger.info("Successfully indexed chat message document", doc_id=chat_message.id)
                messages_processed.inc(labels={"status": "success"})
        except Exception as e:
            logger.error(
                "Failed to process chat message, sending to DLS",
                error=str(e),
                exc_info=True,
            )
            messages_processed.inc(labels={"status": "error"})
            messages_sent_to_dls.inc()
            send_to_dls(
                dls_handler,
                message,
                e,
                settings.mongo_config.database,
                settings.dls_collection,
            )


if __name__ == "__main__":
    main()
