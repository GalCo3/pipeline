from hermes.connections import BaseElasticHandler

# Fields describing a chunk itself rather than its parent, so never part of a diff.
CHUNK_ONLY_FIELDS = frozenset(
    {
        "parent_id",
        "chunk_order",
        "chunk_content",
        "embedding",
        "__chunking_version",
        "__embedding_version",
    }
)


class SourceDocumentNotFoundError(Exception):
    """Raised when the lexical document a trigger message refers to is missing."""


def denormalized_fields(lexical_document: dict, excluded_fields: set[str]) -> dict:
    """The parent fields copied onto every chunk of a document."""
    return {key: value for key, value in lexical_document.items() if key not in excluded_fields}


def fetch_lexical_document(
    elastic_handler: BaseElasticHandler, lexical_index: str, doc_id: str | int
) -> dict:
    """
    The source document a trigger refers to.

    :raises SourceDocumentNotFoundError: If it is not in the lexical index.
    """
    response, _ = elastic_handler.search_by_id(lexical_index, str(doc_id))
    if not response.is_success:
        raise SourceDocumentNotFoundError(f"Document {doc_id} not found in {lexical_index}")
    return (response.response or {})["_source"]


def fetch_first_chunk(
    elastic_handler: BaseElasticHandler, semantic_index: str, doc_id: str | int
) -> dict | None:
    """
    Chunk 0 of `doc_id`, which carries the same metadata as the rest, so a diff
    only has to read one document. None if the document has no chunks indexed.
    """
    response, _ = elastic_handler.search(
        semantic_index,
        {"bool": {"filter": [{"term": {"parent_id": doc_id}}, {"term": {"chunk_order": 0}}]}},
    )
    if not response.is_success:
        return None

    hits = (response.response or {}).get("hits", {}).get("hits", [])
    return hits[0]["_source"] if hits else None


def diff_metadata_fields(lexical_document: dict, chunk_document: dict) -> dict:
    """
    The fields shared by a lexical document and one of its chunks whose values
    differ, mapped to their new (lexical) value.
    """
    shared_keys = (lexical_document.keys() & chunk_document.keys()) - CHUNK_ONLY_FIELDS
    return {
        key: lexical_document[key]
        for key in shared_keys
        if lexical_document[key] != chunk_document[key]
    }
