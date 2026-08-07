from exceptions import CargoFileNotFoundError
from hermes.connections import (
    BaseConsumerHandler,
    BaseElasticHandler,
    BaseMongoHandler,
    BaseS3Handler,
)
from hermes.observability import TelemetryCounter, get_logger, init_observability, kafka_context
from hermes.utils import send_to_dls, site_error
from models import CargoEnrichedMessage, CargoMessage
from settings import get_settings
from utils import extract_cargo_files_text

init_observability(service_name="cargo-lexical")
logger = get_logger(__name__)
messages_processed = TelemetryCounter(
    "cargo_lexical_messages_processed_total", allowed_labels=["status"]
)
messages_sent_to_dls = TelemetryCounter("cargo_lexical_messages_dls_total")

settings = get_settings()


def main():
    consumer_handler = BaseConsumerHandler(settings.consumer_config)
    elastic_handler = BaseElasticHandler(settings.elastic_config)
    dls_handler = BaseMongoHandler(settings.mongo_config)
    cargo_client = BaseS3Handler(settings.cargo_config)

    for message in consumer_handler.start_consuming():
        try:
            with kafka_context(message, name="process_cargo_message"):
                cargo_message = CargoMessage(**message.value())

                if cargo_message.delete_date is not None:
                    local_response, remote_response = elastic_handler.delete_by_id(
                        settings.index_name, cargo_message.id, is_multisite=True
                    )
                    site_error(
                        local_response,
                        remote_response,
                        f"Failed to delete cargo-lexical document {cargo_message.id}",
                    )
                    continue

                if cargo_message.last_modified > cargo_message.ver_last_modified:
                    local_response, remote_response = elastic_handler.update_by_id(
                        settings.index_name,
                        cargo_message.id,
                        {"doc": cargo_message.model_dump()},
                        is_multisite=True,
                    )
                    site_error(
                        local_response,
                        remote_response,
                        f"Failed to update cargo-lexical document {cargo_message.id}",
                    )
                    continue

                extraction_result = extract_cargo_files_text(
                    cargo_client, cargo_message.s3_key, cargo_message.s3_bucket
                )
                if extraction_result is None:
                    messages_processed.inc(labels={"status": "skipped"})
                    continue

                cargo_enriched_message = CargoEnrichedMessage(
                    **cargo_message.model_dump(),
                    text_content=extraction_result.text,
                    type=extraction_result.mime_type,
                )

                local_response, remote_response = elastic_handler.index(
                    settings.index_name,
                    cargo_enriched_message.id,
                    cargo_enriched_message.model_dump(),
                    is_multisite=True,
                )
                site_error(
                    local_response,
                    remote_response,
                    f"Failed to index cargo-lexical document {cargo_enriched_message.id}",
                )
                messages_processed.inc(labels={"status": "success"})
        except CargoFileNotFoundError as e:
            messages_processed.inc(labels={"status": "not_found"})
            messages_sent_to_dls.inc()
            send_to_dls(
                dls_handler, message, e, settings.mongo_config.database, settings.dls_collection
            )
        except Exception as e:
            messages_processed.inc(labels={"status": "error"})
            messages_sent_to_dls.inc()
            send_to_dls(
                dls_handler, message, e, settings.mongo_config.database, settings.dls_collection
            )


if __name__ == "__main__":
    main()
