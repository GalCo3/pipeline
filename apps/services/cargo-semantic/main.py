from exceptions import SourceDocumentNotFoundError
from settings import get_settings
from utils import EMBEDDED_FIELDS, EXCLUDED_FIELDS, TEXT_FIELD

from hermes.connections import BaseConsumerHandler, BaseElasticHandler, BaseMongoHandler
from hermes.observability import (
    MessageStatus,
    TelemetryCounter,
    TelemetryHistogram,
    get_logger,
    init_observability,
    kafka_context,
)
from hermes.utils import (
    SemanticTriggerMessage,
    SentenceChunker,
    TritonEmbedder,
    chunk_and_embed_document,
    delete_chunks,
    denormalized_fields,
    diff_metadata_fields,
    fetch_first_chunk,
    fetch_lexical_document,
    patch_chunk_metadata,
    send_to_dls,
)

init_observability(service_name="cargo-semantic")
logger = get_logger(__name__)
messages_processed = TelemetryCounter(
    "cargo_semantic_messages_processed_total", allowed_labels=["status"]
)
messages_sent_to_dls = TelemetryCounter("cargo_semantic_messages_dls_total")
message_duration = TelemetryHistogram(
    "cargo_semantic_message_duration", unit="s", allowed_labels=["status"]
)


def main():
    settings = get_settings()
    consumer_handler = BaseConsumerHandler(settings.consumer_config)
    elastic_handler = BaseElasticHandler(settings.elastic_config)
    dls_handler = BaseMongoHandler(settings.mongo_config)
    embedder = TritonEmbedder(
        settings.triton_config,
        model_name=settings.embedding_model_name,
        model_version=settings.embedding_model_version,
        tokenizer_name_or_path=settings.tokenizer_name_or_path,
        s3_config=settings.s3_config,
    )
    # Chunk with the tokenizer the embedder already loaded, so a chunk that
    # measures within the limit is the same one the model sees.
    chunker = SentenceChunker(
        tokenizer=embedder.tokenizer.tokenize,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    for message in consumer_handler.start_consuming():
        try:
            with kafka_context(message, name="process_cargo_semantic_message"):
                trigger = SemanticTriggerMessage.model_validate(message.value())
                doc_id = int(trigger.id)
                logger.info(
                    "Processing cargo semantic trigger", doc_id=doc_id, action=trigger.action
                )

                if trigger.action == "delete":
                    with message_duration.time(labels={"status": MessageStatus.DELETED}):
                        delete_chunks(elastic_handler, settings.semantic_index_name, doc_id)
                    logger.info("Deleted cargo chunks", doc_id=doc_id)
                    messages_processed.inc(labels={"status": MessageStatus.DELETED})
                    continue

                if trigger.action == "update_metadata":
                    with message_duration.time(labels={"status": MessageStatus.UPDATED}):
                        lexical_document = fetch_lexical_document(
                            elastic_handler, settings.lexical_index_name, doc_id
                        )
                        chunk_document = fetch_first_chunk(
                            elastic_handler, settings.semantic_index_name, doc_id
                        )

                        if chunk_document is None:
                            logger.warning(
                                "No existing cargo chunks for metadata update, sending to DLS",
                                doc_id=doc_id,
                            )
                            messages_processed.inc(
                                labels={"status": MessageStatus.METADATA_MISSING_CHUNKS}
                            )
                            messages_sent_to_dls.inc()
                            send_to_dls(
                                dls_handler,
                                message,
                                f"No existing chunks found for cargo document {doc_id}",
                                settings.mongo_config.database,
                                settings.dls_collection,
                            )
                            continue

                        changed_fields = diff_metadata_fields(
                            denormalized_fields(lexical_document, EXCLUDED_FIELDS), chunk_document
                        )

                        if not changed_fields:
                            logger.warning("No metadata changes for cargo document", doc_id=doc_id)
                            messages_processed.inc(labels={"status": MessageStatus.METADATA_NOOP})
                        elif changed_fields.keys() & EMBEDDED_FIELDS:
                            chunk_and_embed_document(
                                elastic_handler,
                                embedder,
                                chunker,
                                settings.semantic_index_name,
                                doc_id,
                                text=lexical_document.get(TEXT_FIELD) or "",
                                denormalized_fields=denormalized_fields(
                                    lexical_document, EXCLUDED_FIELDS
                                ),
                            )
                            logger.info(
                                "Re-embedded cargo document after metadata change",
                                doc_id=doc_id,
                                fields=list(changed_fields),
                            )
                            messages_processed.inc(
                                labels={"status": MessageStatus.METADATA_REEMBEDDED}
                            )
                        else:
                            patch_chunk_metadata(
                                elastic_handler,
                                settings.semantic_index_name,
                                doc_id,
                                changed_fields,
                            )
                            logger.info(
                                "Patched cargo chunk metadata",
                                doc_id=doc_id,
                                fields=list(changed_fields),
                            )
                            messages_processed.inc(
                                labels={"status": MessageStatus.METADATA_PATCHED}
                            )
                    continue

                with message_duration.time(labels={"status": MessageStatus.INDEXED}):
                    lexical_document = fetch_lexical_document(
                        elastic_handler, settings.lexical_index_name, doc_id
                    )
                    chunk_and_embed_document(
                        elastic_handler,
                        embedder,
                        chunker,
                        settings.semantic_index_name,
                        doc_id,
                        text=lexical_document.get(TEXT_FIELD) or "",
                        denormalized_fields=denormalized_fields(lexical_document, EXCLUDED_FIELDS),
                    )
                logger.info("Successfully indexed cargo chunks", doc_id=doc_id)
                messages_processed.inc(labels={"status": MessageStatus.INDEXED})
        except SourceDocumentNotFoundError as e:
            logger.warning(
                "Cargo source document not found, sending to DLS",
                error=str(e),
            )
            messages_processed.inc(labels={"status": MessageStatus.NOT_FOUND})
            messages_sent_to_dls.inc()
            send_to_dls(
                dls_handler, message, e, settings.mongo_config.database, settings.dls_collection
            )
        except Exception as e:
            logger.error(
                "Failed to process cargo semantic message, sending to DLS",
                exc_info=True,
            )
            messages_processed.inc(labels={"status": MessageStatus.ERROR})
            messages_sent_to_dls.inc()
            send_to_dls(
                dls_handler, message, e, settings.mongo_config.database, settings.dls_collection
            )


if __name__ == "__main__":
    main()
