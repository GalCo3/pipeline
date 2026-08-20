from hermes.connections import BaseElasticHandler

from ..chunking import CHUNKING_VERSION, SentenceChunker
from ..site import site_error
from ..triton import TritonEmbedder


def build_chunk_documents(
    parent_id: str | int,
    chunks: list[str],
    embeddings: list[list[float]],
    denormalized_fields: dict,
    chunking_version: str,
    embedding_version: str,
) -> list[dict]:
    """Zip chunk texts and their embeddings into semantic index documents."""
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


def delete_chunks(
    elastic_handler: BaseElasticHandler, semantic_index: str, parent_id: str | int
) -> None:
    """Delete every chunk document belonging to `parent_id`."""
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
    Replace every chunk of `parent_id` with `chunk_documents`. Deletes first so a
    shrinking chunk count doesn't leave orphaned trailing chunks behind.
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

    # stream_bulk returns the generator unconsumed, so per-item failures only
    # surface once it is iterated here.
    for response in (local_response, remote_response):
        if response is None or not response.is_success:
            continue
        for ok, item in response.response or []:
            if not ok:
                raise RuntimeError(
                    f"Failed to index a chunk for {parent_id} into {semantic_index}: {item}"
                )


def chunk_and_embed_document(
    elastic_handler: BaseElasticHandler,
    embedder: TritonEmbedder,
    chunker: SentenceChunker,
    semantic_index: str,
    doc_id: str | int,
    text: str,
    denormalized_fields: dict,
) -> None:
    """Chunk and embed `text`, then replace every chunk of `doc_id` with the result."""
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
    """Write changed parent fields onto every chunk of `doc_id` in place."""
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
