from elasticsearch import NotFoundError

from hermes.connections import BaseElasticHandler, SiteResponse
from hermes.observability import MessageStatus, get_logger
from hermes.utils.site import site_error

logger = get_logger(__name__)


def _is_not_found(local_response: SiteResponse, remote_response: SiteResponse | None) -> bool:
    return isinstance(local_response.error, NotFoundError) or (
        remote_response is not None and isinstance(remote_response.error, NotFoundError)
    )


def delete_document(
    handler: BaseElasticHandler, index_name: str, document_id: str
) -> MessageStatus:
    """Delete a document from every configured Elasticsearch site."""
    local_response, remote_response = handler.delete_by_id(
        index_name, document_id, is_multisite=True
    )
    if _is_not_found(local_response, remote_response):
        logger.warning(
            "Document not found for deletion",
            index_name=index_name,
            doc_id=document_id,
        )
        return MessageStatus.NOT_FOUND

    site_error(
        local_response,
        remote_response,
        f"Failed to delete {index_name} document {document_id}",
    )
    logger.info("Deleted document", index_name=index_name, doc_id=document_id)
    return MessageStatus.DELETED
