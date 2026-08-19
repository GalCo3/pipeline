from unittest.mock import Mock

import pytest
from elastic_transport import ApiResponseMeta, NodeConfig
from elasticsearch import NotFoundError

from hermes.connections import SiteResponse
from hermes.observability import MessageStatus
from hermes.utils import delete_document


def _not_found_error() -> NotFoundError:
    meta = ApiResponseMeta(
        status=404,
        http_version="1.1",
        headers={},
        duration=0,
        node=NodeConfig("http", "localhost", 9200),
    )
    return NotFoundError("missing", meta, None)


def test_delete_document_deletes_from_all_sites() -> None:
    handler = Mock()
    handler.delete_by_id.return_value = (
        SiteResponse(is_success=True),
        SiteResponse(is_success=True),
    )

    status = delete_document(handler, "documents", "42")

    assert status is MessageStatus.DELETED
    handler.delete_by_id.assert_called_once_with("documents", "42", is_multisite=True)


@pytest.mark.parametrize("missing_site", ["local", "remote"])
def test_delete_document_preserves_multisite_not_found_status(
    missing_site: str,
) -> None:
    local = SiteResponse(is_success=True)
    remote = SiteResponse(is_success=True)
    if missing_site == "local":
        local = SiteResponse(is_success=False, error=_not_found_error())
    else:
        remote = SiteResponse(is_success=False, error=_not_found_error())
    handler = Mock()
    handler.delete_by_id.return_value = local, remote

    assert delete_document(handler, "documents", "42") is MessageStatus.NOT_FOUND


def test_delete_document_raises_other_site_errors() -> None:
    error = RuntimeError("unavailable")
    handler = Mock()
    handler.delete_by_id.return_value = (
        SiteResponse(is_success=True),
        SiteResponse(is_success=False, error=error),
    )

    with pytest.raises(RuntimeError, match="Failed to delete documents document 42") as exc:
        delete_document(handler, "documents", "42")

    assert exc.value.__cause__ is error
