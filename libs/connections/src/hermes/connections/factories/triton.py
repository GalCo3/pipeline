import logging
from urllib.parse import urljoin
import requests

from ..config_models.triton import BaseTritonConfig, BaseTritonSiteConfig

logger = logging.getLogger(__name__)


class TritonClientSession:
    """Synchronous HTTP session wrapper for Triton REST v2 API endpoints."""

    def __init__(self, base_url: str, headers: dict[str, str], timeout: int):
        self.base_url = base_url if base_url.endswith("/") else f"{base_url}/"
        self.session = requests.Session()
        self.session.headers.update(headers)
        self.timeout = timeout

    def post(self, path: str, json_data: dict) -> dict:
        url = urljoin(self.base_url, path.lstrip("/"))
        resp = self.session.post(url, json=json_data, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get(self, path: str) -> dict | bool:
        url = urljoin(self.base_url, path.lstrip("/"))
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        if "application/json" in resp.headers.get("content-type", ""):
            return resp.json()
        return resp.status_code == 200

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def create_triton_raw_client(config: BaseTritonSiteConfig) -> TritonClientSession:
    headers = {}
    if config.infer_token:
        headers["X-Triton-Consume"] = config.infer_token
        headers["Authorization"] = f"Bearer {config.infer_token}"
    if config.manage_token:
        headers["X-Triton-Manage"] = config.manage_token

    endpoint = config.endpoint
    if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
        endpoint = f"http://{endpoint}"

    return TritonClientSession(
        base_url=endpoint,
        headers=headers,
        timeout=config.timeout_seconds,
        verify_ssl=config.verify_ssl,
    )


def create_triton_clients(
    config: BaseTritonConfig,
) -> tuple[TritonClientSession, TritonClientSession | None]:
    """
    Creates local and optional remote TritonClientSession objects.
    """
    local_client = create_triton_raw_client(config.local_site)
    remote_client = (
        create_triton_raw_client(config.remote_site)
        if config.remote_site is not None
        else None
    )

    logger.info("Created local Triton client", extra={"endpoint": config.local_site.endpoint})
    if remote_client:
        logger.info("Created remote Triton client", extra={"endpoint": config.remote_site.endpoint})

    return local_client, remote_client
