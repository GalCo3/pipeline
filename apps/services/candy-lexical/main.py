from models import CandyReportsMessage
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

init_observability(service_name="candy-lexical")
logger = get_logger(__name__)
messages_processed = TelemetryCounter(
    "candy_lexical_messages_processed_total", allowed_labels=["status"]
)
messages_sent_to_dls = TelemetryCounter("candy_lexical_messages_dls_total")
message_duration = TelemetryHistogram(
    "candy_lexical_message_duration", unit="s", allowed_labels=["status"]
)


def main():
    settings = get_settings()
    consumer_handler = BaseConsumerHandler(settings.consumer_config)
    elastic_handler = BaseElasticHandler(settings.elastic_config)
    dls_handler = BaseMongoHandler(settings.mongo_config)

    for message in consumer_handler.start_consuming():
        try:
            with kafka_context(message, name="process_candy_reports_message"):
                candy_reports_message = CandyReportsMessage.model_validate(message.value())
                doc_id = candy_reports_message.id
                logger.info("Processing candy reports message", doc_id=doc_id)

                if candy_reports_message.is_deleted:
                    with message_duration.time(labels={"status": "deleted"}):
                        local_response, remote_response = elastic_handler.delete_by_id(
                            settings.index_name, doc_id, is_multisite=True
                        )
                        site_error(
                            local_response,
                            remote_response,
                            f"Failed to delete candy-lexical document {doc_id}",
                        )
                    logger.info("Deleted candy reports document", doc_id=doc_id)
                    messages_processed.inc(labels={"status": "deleted"})
                    continue

                with message_duration.time(labels={"status": "indexed"}):
                    local_response, remote_response = elastic_handler.index(
                        settings.index_name,
                        doc_id,
                        with_indexed_at(candy_reports_message.model_dump(mode="json")),
                        is_multisite=True,
                    )
                    site_error(
                        local_response,
                        remote_response,
                        f"Failed to index candy-lexical document {doc_id}",
                    )
                logger.info("Successfully indexed candy reports document", doc_id=doc_id)
                messages_processed.inc(labels={"status": "indexed"})
        except Exception as e:
            logger.error(
                "Failed to process candy reports message, sending to DLS",
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
