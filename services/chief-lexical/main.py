from exceptions import ChiefAPIError
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
from hermes.utils import send_to_dls, site_error
from models import ChiefEnrichedMessage, ChiefMessage
from settings import get_settings
from utils import convert_chief_command, extract_chief_command_content

init_observability(service_name="chief-lexical")
logger = get_logger(__name__)
messages_processed = TelemetryCounter(
    "chief_lexical_messages_processed_total", allowed_labels=["status"]
)
messages_sent_to_dls = TelemetryCounter("chief_lexical_messages_dls_total")
message_duration = TelemetryHistogram(
    "chief_lexical_message_duration", unit="s", allowed_labels=["status"]
)

settings = get_settings()


def main():
    consumer_handler = BaseConsumerHandler(settings.consumer_config)
    elastic_handler = BaseElasticHandler(settings.elastic_config)
    dls_handler = BaseMongoHandler(settings.mongo_config)

    for message in consumer_handler.start_consuming():
        try:
            with kafka_context(message, name="process_chief_message"):
                chief_message = ChiefMessage(**message.value())
                logger.info("Processing chief message", doc_id=chief_message.id)

                if chief_message.is_deleted:
                    with message_duration.time(labels={"status": "deleted"}):
                        local_response, remote_response = elastic_handler.delete_by_id(
                            settings.index_name, chief_message.id, is_multisite=True
                        )
                        site_error(
                            local_response,
                            remote_response,
                            f"Failed to delete chief-lexical document {chief_message.id}",
                        )
                    logger.info("Deleted chief document", doc_id=chief_message.id)
                    messages_processed.inc(labels={"status": "deleted"})
                    continue

                if chief_message.metro_last_update_date > chief_message.content_last_update_date:
                    with message_duration.time(labels={"status": "updated"}):
                        local_response, remote_response = elastic_handler.update_by_id(
                            settings.index_name,
                            chief_message.id,
                            {"doc": chief_message.model_dump(mode="json")},
                            is_multisite=True,
                        )
                        site_error(
                            local_response,
                            remote_response,
                            f"Failed to update chief-lexical document {chief_message.id}",
                        )
                    logger.info("Updated chief document metadata", doc_id=chief_message.id)
                    messages_processed.inc(labels={"status": "updated"})
                    continue

                with message_duration.time(labels={"status": "indexed"}):
                    command_content = extract_chief_command_content(
                        id=chief_message.id,
                        doc_path_template=settings.chief_config.doc_path_template,
                        api_key=settings.chief_config.api_key.get_secret_value(),
                        timeout=settings.chief_config.timeout,
                    )
                    
                    cleaned_text = convert_chief_command(chief_message.name, command_content)

                    chief_enriched_message = ChiefEnrichedMessage(
                        **chief_message.model_dump(mode="json"),
                        command_content=command_content,
                        cleaned_text=cleaned_text,
                    )

                    local_response, remote_response = elastic_handler.index(
                        settings.index_name,
                        chief_enriched_message.id,
                        chief_enriched_message.model_dump(mode="json"),
                        is_multisite=True,
                    )
                    site_error(
                        local_response,
                        remote_response,
                        f"Failed to index chief-lexical document {chief_enriched_message.id}",
                    )
                logger.info("Successfully indexed chief document", doc_id=chief_message.id)
                messages_processed.inc(labels={"status": "indexed"})
        except ChiefAPIError as e:
            logger.warning(
                "Chief API error, sending message to DLS",
                error=str(e),
                topic=message.topic(),
            )
            messages_processed.inc(labels={"status": "not_found"})
            messages_sent_to_dls.inc()
            send_to_dls(
                dls_handler, message, e, settings.mongo_config.database, settings.dls_collection
            )
        except Exception as e:
            logger.error(
                "Failed to process chief message, sending to DLS",
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
