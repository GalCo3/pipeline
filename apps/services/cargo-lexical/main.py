from elasticsearch import NotFoundError
from exceptions import CargoFileNotFoundError
from models import CargoEnrichedMessage, CargoMessage
from settings import get_settings
from utils import extract_cargo_files_text

from hermes.connections import (
    BaseConsumerHandler,
    BaseElasticHandler,
    BaseMongoHandler,
    BaseS3Handler,
)
from hermes.observability import (
    MessageStatus,
    TelemetryCounter,
    TelemetryHistogram,
    get_logger,
    init_observability,
    kafka_context,
)
from hermes.utils import send_to_dls, site_error, with_indexed_at

init_observability(service_name="cargo-lexical")
logger = get_logger(__name__)
messages_processed = TelemetryCounter(
    "cargo_lexical_messages_processed_total", allowed_labels=["status"]
)
messages_sent_to_dls = TelemetryCounter("cargo_lexical_messages_dls_total")
message_duration = TelemetryHistogram(
    "cargo_lexical_message_duration", unit="s", allowed_labels=["status"]
)


def _is_not_found(response, remote_response=None) -> bool:
    return isinstance(response.error, NotFoundError) or (
        remote_response is not None and isinstance(remote_response.error, NotFoundError)
    )


def _delete_cargo_document(
    elastic_handler: BaseElasticHandler,
    settings,
    cargo_message: CargoMessage,
) -> str:
    with message_duration.time(labels={"status": MessageStatus.DELETED}):
        local_response, remote_response = elastic_handler.delete_by_id(
            settings.index_name, cargo_message.id, is_multisite=True
        )
        if _is_not_found(local_response, remote_response):
            logger.warning("Cargo document not found for deletion", doc_id=cargo_message.id)
            return MessageStatus.NOT_FOUND

        site_error(
            local_response,
            remote_response,
            f"Failed to delete cargo-lexical document {cargo_message.id}",
        )
    logger.info("Deleted cargo document", doc_id=cargo_message.id)
    return MessageStatus.DELETED


def _update_cargo_document_metadata(
    cargo_client: BaseS3Handler,
    elastic_handler: BaseElasticHandler,
    settings,
    cargo_message: CargoMessage,
) -> str:
    with message_duration.time(labels={"status": MessageStatus.UPDATED}):
        local_response, remote_response = elastic_handler.update_by_id(
            settings.index_name,
            cargo_message.id,
            {"doc": with_indexed_at(cargo_message.model_dump(mode="json"))},
            is_multisite=True,
        )
        if _is_not_found(local_response, remote_response):
            logger.info(
                "Cargo document missing for metadata update, falling back to index",
                doc_id=cargo_message.id,
            )
        else:
            site_error(
                local_response,
                remote_response,
                f"Failed to update cargo-lexical document {cargo_message.id}",
            )
            logger.info("Updated cargo document metadata", doc_id=cargo_message.id)
            return MessageStatus.UPDATED

    return _index_cargo_document(
        cargo_client, elastic_handler, settings, cargo_message
    )


def _index_cargo_document(
    cargo_client: BaseS3Handler,
    elastic_handler: BaseElasticHandler,
    settings,
    cargo_message: CargoMessage,
) -> str:
    with message_duration.time(labels={"status": MessageStatus.INDEXED}):
        extraction_result = extract_cargo_files_text(
            cargo_client, cargo_message.s3_key, cargo_message.s3_bucket
        )
        if extraction_result is None:
            logger.warning("Skipped cargo text extraction", doc_id=cargo_message.id)
            return MessageStatus.SKIPPED

        cargo_enriched_message = CargoEnrichedMessage(
            **cargo_message.model_dump(mode="json"),
            text_content=extraction_result.text,
            type=extraction_result.mime_type,
        )

        local_response, remote_response = elastic_handler.index(
            settings.index_name,
            cargo_enriched_message.id,
            with_indexed_at(cargo_enriched_message.model_dump(mode="json")),
            is_multisite=True,
        )
        site_error(
            local_response,
            remote_response,
            f"Failed to index cargo-lexical document {cargo_enriched_message.id}",
        )
    logger.info("Successfully indexed cargo document", doc_id=cargo_message.id)
    return MessageStatus.INDEXED


def main():
    settings = get_settings()
    consumer_handler = BaseConsumerHandler(settings.consumer_config)
    elastic_handler = BaseElasticHandler(settings.elastic_config)
    dls_handler = BaseMongoHandler(settings.mongo_config)
    cargo_client = BaseS3Handler(settings.cargo_config)

    for message in consumer_handler.start_consuming():
        try:
            with kafka_context(message, name="process_cargo_message"):
                cargo_message = CargoMessage.model_validate(message.value())
                logger.info("Processing cargo message", doc_id=cargo_message.id)

                if cargo_message.delete_date is not None:
                    status = _delete_cargo_document(
                        elastic_handler, settings, cargo_message
                    )
                    messages_processed.inc(labels={"status": status})
                    continue

                if cargo_message.last_modified > cargo_message.ver_last_modified:
                    status = _update_cargo_document_metadata(
                        cargo_client, elastic_handler, settings, cargo_message
                    )
                    messages_processed.inc(labels={"status": status})
                    continue

                status = _index_cargo_document(
                    cargo_client, elastic_handler, settings, cargo_message
                )
                messages_processed.inc(labels={"status": status})
        except CargoFileNotFoundError as e:
            logger.warning(
                "Cargo file not found, sending message to DLS",
                error=str(e),
                topic=message.topic(),
            )
            messages_processed.inc(labels={"status": MessageStatus.NOT_FOUND})
            messages_sent_to_dls.inc()
            send_to_dls(
                dls_handler, message, e, settings.mongo_config.database, settings.dls_collection
            )
        except Exception as e:
            logger.error(
                "Failed to process cargo message, sending to DLS",
                error=str(e),
                exc_info=True,
            )
            messages_processed.inc(labels={"status": MessageStatus.ERROR})
            messages_sent_to_dls.inc()
            send_to_dls(
                dls_handler, message, e, settings.mongo_config.database, settings.dls_collection
            )


if __name__ == "__main__":
    main()
