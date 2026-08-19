from exceptions import SourceDocumentNotFoundError
from settings import Settings

from hermes.connections import BaseElasticHandler
from hermes.semantic_enrichment import CHUNKING_VERSION, BaseEmbeddingHandler, chunk_text
from hermes.utils import build_chunk_documents, replace_chunks

# ChiefEnrichedMessage.cleaned_text is `name` followed by the fetched command
# content — `name` is the only ChiefMessage field baked into the embedded text,
# everything else on the message is pure metadata.
TEXT_FIELD = "cleaned_text"
EMBEDDED_FIELDS = {"name"}

# Fields written by cargo-lexical/chief-lexical that never belong on a chunk
# document (large text bodies, pipeline-internal bookkeeping).
EXCLUDED_FIELDS = {TEXT_FIELD, "command_content", "indexed_at"}


def denormalized_fields(lexical_document: dict) -> dict:
    return {key: value for key, value in lexical_document.items() if key not in EXCLUDED_FIELDS}


def fetch_lexical_document(
    elastic_handler: BaseElasticHandler, settings: Settings, doc_id: str
) -> dict:
    response, _ = elastic_handler.search_by_id(settings.lexical_index_name, doc_id)
    if not response.is_success:
        raise SourceDocumentNotFoundError(
            f"Chief document {doc_id} not found in {settings.lexical_index_name}"
        )
    return (response.response or {})["_source"]


def fetch_first_chunk(
    elastic_handler: BaseElasticHandler, settings: Settings, doc_id: str
) -> dict | None:
    response, _ = elastic_handler.search(
        settings.semantic_index_name,
        {"bool": {"filter": [{"term": {"parent_id": doc_id}}, {"term": {"chunk_order": 0}}]}},
    )
    if not response.is_success:
        return None

    hits = (response.response or {}).get("hits", {}).get("hits", [])
    return hits[0]["_source"] if hits else None


def chunk_and_embed_document(
    elastic_handler: BaseElasticHandler,
    embedding_handler: BaseEmbeddingHandler,
    settings: Settings,
    doc_id: str,
    lexical_document: dict | None = None,
) -> None:
    """Chunk, embed and replace every chunk of `doc_id` in the semantic index."""
    if lexical_document is None:
        lexical_document = fetch_lexical_document(elastic_handler, settings, doc_id)

    chunks = chunk_text(
        lexical_document.get(TEXT_FIELD) or "", settings.chunk_size, settings.chunk_overlap
    )
    embeddings = embedding_handler.embed(chunks)

    chunk_documents = build_chunk_documents(
        parent_id=doc_id,
        chunks=chunks,
        embeddings=embeddings,
        denormalized_fields=denormalized_fields(lexical_document),
        chunking_version=CHUNKING_VERSION,
        embedding_version=settings.triton_config.embedding_version,
    )

    replace_chunks(elastic_handler, settings.semantic_index_name, doc_id, chunk_documents)
