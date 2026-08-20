from typing import Literal

from pydantic import BaseModel, ConfigDict

from hermes.connections import BaseElasticHandler, BasePlainProducerHandler
from hermes.observability import get_logger

from .chunking import CHUNKING_VERSION, SentenceChunker
from .site import site_error
from .triton import TritonEmbedder

logger = get_logger(__name__)

SemanticAction = Literal["delete", "update_metadata", "index"]


class SourceDocumentNotFoundError(Exception):
    """Raised when the lexical document a trigger message refers to is missing."""


# Fields that describe a chunk itself rather than its parent document, so they
# never belong in a lexical/chunk metadata diff.
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


class SemanticTriggerMessage(BaseModel):
    """The message cargo-lexical/chief-lexical publish for cargo-semantic/chief-semantic."""

    model_config = ConfigDict(extra="forbid")

    id: str | int
    action: SemanticAction


def produce_semantic_trigger(
    producer_handler: BasePlainProducerHandler,
    topic: str,
    doc_id: str | int,
    action: SemanticAction,
) -> None:
    """
    Tell the semantic sibling service (cargo-semantic, chief-semantic) that a
    lexical document was deleted, had its metadata updated, or was (re)indexed.

    :param producer_handler: The lexical service's Kafka producer.
    :param topic: The semantic trigger topic to publish to.
    :param doc_id: The document id, shared between the lexical and semantic indices.
    :param action: What happened to the document.
    """
    key = str(doc_id)
    producer_handler.produce_message(
        topic=topic, key=key, value={"id": doc_id, "action": action}, headers={}
    )
    producer_handler.flush()
    logger.info("Produced semantic trigger", topic=topic, doc_id=doc_id, action=action)


def delete_chunks(
    elastic_handler: BaseElasticHandler, semantic_index: str, parent_id: str | int
) -> None:
    """Delete every chunk document belonging to `parent_id` from a semantic index."""
    local_response, remote_response = elastic_handler.delete_by_query(
        semantic_index, {"term": {"parent_id": parent_id}}, is_multisite=True
    )
    site_error(
        local_response,
        remote_response,
        f"Failed to delete chunks for {parent_id} from {semantic_index}",
    )


def replace_chunks(
    elastic_handler: BaseElasticHandler,
    semantic_index: str,
    parent_id: str | int,
    chunk_documents: list[dict],
) -> None:
    """
    Replace every chunk document belonging to `parent_id` in a semantic index with
    `chunk_documents`. Deletes first so a shrinking chunk count doesn't leave
    orphaned trailing chunks behind.

    :param elastic_handler: The Elasticsearch handler for the semantic index.
    :param semantic_index: The semantic index/alias name.
    :param parent_id: The lexical document id these chunks belong to.
    :param chunk_documents: Documents built by `build_chunk_documents`.
    """
    delete_chunks(elastic_handler, semantic_index, parent_id)

    if not chunk_documents:
        return

    actions = [
        {
            "_op_type": "index",
            "_index": semantic_index,
            "_id": f"{parent_id}_{chunk['chunk_order']}",
            "_source": chunk,
        }
        for chunk in chunk_documents
    ]

    local_response, remote_response = elastic_handler.stream_bulk(actions, is_multisite=True)
    site_error(
        local_response,
        remote_response,
        f"Failed to index chunks for {parent_id} into {semantic_index}",
    )

    # stream_bulk hands back the raw streaming_bulk() generator unconsumed, so
    # per-item failures only surface once it's iterated here.
    for response in (local_response, remote_response):
        if response is None or not response.is_success:
            continue
        for ok, item in response.response or []:
            if not ok:
                raise RuntimeError(
                    f"Failed to index a chunk for {parent_id} into {semantic_index}: {item}"
                )


def build_chunk_documents(
    parent_id: str | int,
    chunks: list[str],
    embeddings: list[list[float]],
    denormalized_fields: dict,
    chunking_version: str,
    embedding_version: str,
) -> list[dict]:
    """
    Zip chunk text and embeddings into semantic index documents, each carrying the
    parent's denormalized metadata fields plus its own chunk_order/chunk_content/embedding.

    :param parent_id: The lexical document id these chunks belong to.
    :param chunks: Ordered chunk texts, from `SentenceChunker.chunk_text`.
    :param embeddings: One embedding vector per chunk, in the same order.
    :param denormalized_fields: The parent's fields to copy onto every chunk.
    :param chunking_version: Stamped as `__chunking_version` on every chunk.
    :param embedding_version: Stamped as `__embedding_version` on every chunk.
    """
    return [
        {
            **denormalized_fields,
            "parent_id": parent_id,
            "chunk_order": order,
            "chunk_content": chunk,
            "embedding": embedding,
            "__chunking_version": chunking_version,
            "__embedding_version": embedding_version,
        }
        for order, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True))
    ]


def diff_metadata_fields(lexical_document: dict, chunk_document: dict) -> dict:
    """
    Return the fields present in both a lexical document and an existing semantic
    chunk whose values differ.

    Compares only keys shared by both dicts — chunk-only fields (see
    `CHUNK_ONLY_FIELDS`) and lexical-only fields (e.g. `indexed_at`, extracted text)
    are ignored since they can't be part of a metadata-only diff.

    :param lexical_document: The current document from the lexical index.
    :param chunk_document: An existing chunk (e.g. chunk_order 0) from the semantic index.
    :return: A mapping of changed field name to its new (lexical) value.
    """
    shared_keys = (lexical_document.keys() & chunk_document.keys()) - CHUNK_ONLY_FIELDS
    return {
        key: lexical_document[key]
        for key in shared_keys
        if lexical_document[key] != chunk_document[key]
    }


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
    Chunk 0 of `doc_id`, which carries the same denormalized metadata as the rest,
    so a metadata diff only has to read one document.

    :return: The chunk, or None if the document has no chunks indexed.
    """
    response, _ = elastic_handler.search(
        semantic_index,
        {"bool": {"filter": [{"term": {"parent_id": doc_id}}, {"term": {"chunk_order": 0}}]}},
    )
    if not response.is_success:
        return None

    hits = (response.response or {}).get("hits", {}).get("hits", [])
    return hits[0]["_source"] if hits else None


def chunk_and_embed_document(
    elastic_handler: BaseElasticHandler,
    embedder: TritonEmbedder,
    chunker: SentenceChunker,
    semantic_index: str,
    doc_id: str | int,
    text: str,
    denormalized_fields: dict,
) -> None:
    """
    Chunk and embed `text`, then replace every chunk of `doc_id` with the result.

    :param elastic_handler: The handler for the semantic index.
    :param embedder: The Triton embedder the chunks are vectorised with.
    :param chunker: The chunker, measuring in `embedder`'s tokenizer's tokens.
    :param semantic_index: The semantic index/alias chunks are written to.
    :param doc_id: The lexical document id the chunks belong to.
    :param text: The lexical field's text to chunk and embed.
    :param denormalized_fields: The parent fields to copy onto every chunk.
    """
    chunks = chunker.chunk_text(text)
    embeddings = embedder.embed_batched(chunks)

    chunk_documents = build_chunk_documents(
        parent_id=doc_id,
        chunks=chunks,
        embeddings=embeddings,
        denormalized_fields=denormalized_fields,
        chunking_version=CHUNKING_VERSION,
        embedding_version=embedder.model_tag,
    )

    replace_chunks(elastic_handler, semantic_index, doc_id, chunk_documents)


def patch_chunk_metadata(
    elastic_handler: BaseElasticHandler,
    semantic_index: str,
    doc_id: str | int,
    fields: dict,
) -> None:
    """
    Write changed parent fields onto every chunk of `doc_id` in place, for a
    metadata change that leaves the embedded text untouched.
    """
    local_response, remote_response = elastic_handler.update_by_query(
        semantic_index,
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
    site_error(local_response, remote_response, f"Failed to patch chunk metadata for {doc_id}")
