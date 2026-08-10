from datetime import UTC, datetime

INDEXED_AT_FIELD = "indexed_at"


def with_indexed_at(document: dict, field: str = INDEXED_AT_FIELD) -> dict:
    """
    Stamp a document with the moment the pipeline handed it to Elasticsearch.

    A message carries the timestamps its source system knows about; this is the
    pipeline's own, so how fresh a document is can be told apart from how recent
    its subject is.

    :param document: The document about to be indexed or updated. Not mutated.
    :param field: The field to stamp under.
    :return: A copy of `document` carrying the timestamp.
    """
    return {**document, field: datetime.now(UTC).isoformat()}
