import logging

from ..config_models.triton import BaseTritonConfig
from ..factories.triton import create_triton_clients, TritonClientSession
from ..models import SiteResponse
from ..utils import execute_on_client

logger = logging.getLogger(__name__)


class BaseTritonHandler:
    """Synchronous connection handler for Triton Inference Server REST v2 API."""

    local_client: TritonClientSession
    remote_client: TritonClientSession | None = None

    def __init__(self, config: BaseTritonConfig):
        if not hasattr(self, "local_client"):
            self.local_client, self.remote_client = create_triton_clients(config)

    def _execute(
        self,
        method: str,
        path: str,
        json_data: dict | None = None,
        is_multisite: bool = False,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """Helper method to execute GET or POST on local and optional remote clients."""
        client_fn = getattr(self.local_client, method)
        args = (path, json_data) if json_data is not None else (path,)
        
        local_response = execute_on_client(client_fn, *args)
        remote_response: SiteResponse | None = None

        if is_multisite and self.remote_client:
            remote_fn = getattr(self.remote_client, method)
            remote_response = execute_on_client(remote_fn, *args)

        return local_response, remote_response

    def infer(
        self,
        model_name: str,
        inputs: list[dict],
        outputs: list[dict] | None = None,
        model_version: str = "1",
        is_multisite: bool = False,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """Execute an inference request on Triton using the v2 REST API protocol."""
        payload = {"inputs": inputs}
        if outputs:
            payload["outputs"] = outputs

        path = f"v2/models/{model_name}/versions/{model_version}/infer"
        return self._execute("post", path, json_data=payload, is_multisite=is_multisite)

    def is_model_ready(
        self,
        model_name: str,
        model_version: str = "1",
        is_multisite: bool = False,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """Check if a model is ready on Triton."""
        path = f"v2/models/{model_name}/versions/{model_version}/ready"
        return self._execute("get", path, is_multisite=is_multisite)

    def get_model_config(
        self,
        model_name: str,
        model_version: str = "1",
        is_multisite: bool = False,
    ) -> tuple[SiteResponse, SiteResponse | None]:
        """Get the configuration of a model on Triton."""
        path = f"v2/models/{model_name}/versions/{model_version}/config"
        return self._execute("get", path, is_multisite=is_multisite)

    def _get_config_field(self, model_name: str, model_version: str, field: str, default: str | int | list | dict):
        local_resp, _ = self.get_model_config(model_name, model_version)
        if not local_resp.is_success:
            raise RuntimeError(f"Failed to get config for model '{model_name}': {local_resp.error}")
        return local_resp.response.get(field, default)

    def get_model_output_names(self, model_name: str, model_version: str = "1") -> list[str]:
        """Extract output names from the local client config."""
        outputs = self._get_config_field(model_name, model_version, "output", [])
        return [out.get("name") for out in outputs if "name" in out]

    def get_model_batch_size(self, model_name: str, model_version: str = "1") -> int:
        """Extract max batch size from the local client config."""
        return self._get_config_field(model_name, model_version, "max_batch_size", 0)

    def get_model_input_dtypes(self, model_name: str, model_version: str = "1") -> dict[str, str]:
        """Extract input data types from the local client config."""
        inputs = self._get_config_field(model_name, model_version, "input", [])
        return {inp["name"]: inp["data_type"] for inp in inputs if "name" in inp and "data_type" in inp}

    def close(self):
        if self.remote_client:
            self.remote_client.close()
        if self.local_client:
            self.local_client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
