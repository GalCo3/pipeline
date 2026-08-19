from exceptions import SourceDocumentNotFoundError
from settings import get_settings
from utils import (
    EMBEDDED_FIELDS,
    chunk_and_embed_document,
    denormalized_fields,
    fetch_first_chunk,
    fetch_lexical_document,
)

from hermes.connections import BaseConsumerHandler, BaseElasticHandler, BaseMongoHandler
from hermes.observability import (
    MessageStatus,
    TelemetryCounter,
    TelemetryHistogram,
    get_logger,
    init_observability,
    kafka_context,
)
from hermes.semantic_enrichment import BaseEmbeddingHandler
from hermes.utils import (
    SemanticTriggerMessage,
    delete_chunks,
    diff_metadata_fields,
    send_to_dls,
    site_error,
)

init_observability(service_name="chief-semantic")
logger = get_logger(__name__)
messages_processed = TelemetryCounter(
    "chief_semantic_messages_processed_total", allowed_labels=["status"]
)
messages_sent_to_dls = TelemetryCounter("chief_semantic_messages_dls_total")
message_duration = TelemetryHistogram(
    "chief_semantic_message_duration", unit="s", allowed_labels=["status"]
)


def _patch_metadata(
    elastic_handler: BaseElasticHandler, semantic_index_name: str, doc_id: str, fields: dict
) -> None:
    local_response, remote_response = elastic_handler.update_by_query(
        semantic_index_name,
        {
            "query": {"term": {"parent_id": doc_id}},
            "script": {
                "lang": "painless",
                "source": (
                    "for (entry in params.fields.entrySet()) "
                    "{ ctx._source[entry.getKey()] = entry.getValue() }"
                ),
                "params": {"fields": fields},
            },
        },
        is_multisite=True,
    )
    site_error(
        local_response, remote_response, f"Failed to patch chief chunk metadata for {doc_id}"
    )


def main():
    settings = get_settings()
    consumer_handler = BaseConsumerHandler(settings.consumer_config)
    elastic_handler = BaseElasticHandler(settings.elastic_config)
    dls_handler = BaseMongoHandler(settings.mongo_config)
    embedding_handler = BaseEmbeddingHandler(settings.triton_config)

    for message in consumer_handler.start_consuming():
        try:
            with kafka_context(message, name="process_chief_semantic_message"):
                trigger = SemanticTriggerMessage.model_validate(message.value())
                doc_id = str(trigger.id)
                logger.info(
                    "Processing chief semantic trigger", doc_id=doc_id, action=trigger.action
                )

                if trigger.action == "delete":
                    with message_duration.time(labels={"status": MessageStatus.DELETED}):
                        delete_chunks(elastic_handler, settings.semantic_index_name, doc_id)
                    logger.info("Deleted chief chunks", doc_id=doc_id)
                    messages_processed.inc(labels={"status": MessageStatus.DELETED})
                    continue

                if trigger.action == "update_metadata":
                    with message_duration.time(labels={"status": MessageStatus.UPDATED}):
                        lexical_document = fetch_lexical_document(elastic_handler, settings, doc_id)
                        chunk_document = fetch_first_chunk(elastic_handler, settings, doc_id)

                        if chunk_document is None:
                            logger.warning(
                                "No existing chief chunks for metadata update, sending to DLS",
                                doc_id=doc_id,
                            )
                            messages_processed.inc(labels={"status": MessageStatus.METADATA_MISSING_CHUNKS})
                            messages_sent_to_dls.inc()
                            send_to_dls(
                                dls_handler,
                                message,
                                f"No existing chunks found for chief document {doc_id}",
                                settings.mongo_config.database,
                                settings.dls_collection,
                            )
                            continue

                        changed_fields = diff_metadata_fields(
                            denormalized_fields(lexical_document), chunk_document
                        )

                        if not changed_fields:
                            logger.warning("No metadata changes for chief document", doc_id=doc_id)
                            messages_processed.inc(labels={"status": MessageStatus.METADATA_NOOP})
                        elif changed_fields.keys() & EMBEDDED_FIELDS:
                            chunk_and_embed_document(
                                elastic_handler,
                                embedding_handler,
                                settings,
                                doc_id,
                                lexical_document,
                            )
                            logger.info(
                                "Re-embedded chief document after metadata change",
                                doc_id=doc_id,
                                fields=list(changed_fields),
                            )
                            messages_processed.inc(labels={"status": MessageStatus.METADATA_REEMBEDDED})
                        else:
                            _patch_metadata(
                                elastic_handler,
                                settings.semantic_index_name,
                                doc_id,
                                changed_fields,
                            )
                            logger.info(
                                "Patched chief chunk metadata",
                                doc_id=doc_id,
                                fields=list(changed_fields),
                            )
                            messages_processed.inc(labels={"status": MessageStatus.METADATA_PATCHED})
                    continue

                with message_duration.time(labels={"status": MessageStatus.INDEXED}):
                    chunk_and_embed_document(elastic_handler, embedding_handler, settings, doc_id)
                logger.info("Successfully indexed chief chunks", doc_id=doc_id)
                messages_processed.inc(labels={"status": MessageStatus.INDEXED})
        except SourceDocumentNotFoundError as e:
            logger.warning(
                "Chief source document not found, sending to DLS",
                error=str(e),
            )
            messages_processed.inc(labels={"status": MessageStatus.NOT_FOUND})
            messages_sent_to_dls.inc()
            send_to_dls(
                dls_handler, message, e, settings.mongo_config.database, settings.dls_collection
            )
        except Exception as e:
            logger.error(
                "Failed to process chief semantic message, sending to DLS",
                exc_info=True,
            )
            messages_processed.inc(labels={"status": MessageStatus.ERROR})
            messages_sent_to_dls.inc()
            send_to_dls(
                dls_handler, message, e, settings.mongo_config.database, settings.dls_collection
            )


if __name__ == "__main__":
    main()
