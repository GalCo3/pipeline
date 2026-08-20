import logging
from typing import Any

from ..config_models.llm import BaseLLMConfig
from ..factories.llm import create_llm_session
from ..models import SiteResponse
from ..utils import execute_on_client

logger = logging.getLogger(__name__)


class BaseLLMHandler:
    """Synchronous connection handler for LLM APIs (OpenAI format)."""

    def __init__(self, config: BaseLLMConfig):
        self.config = config
        self.client = create_llm_session(config)

    def _execute(
        self,
        method: str,
        path: str,
        json_data: dict | None = None,
    ) -> SiteResponse:
        """Helper method to execute GET or POST on the client."""
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        client_fn = getattr(self.client, method)

        def _request():
            response = client_fn(url, json=json_data, timeout=self.config.timeout)
            response.raise_for_status()
            return response.json()

        return execute_on_client(_request)

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 1.0,
        top_p: float = 0.95,
        **kwargs: Any,
    ) -> SiteResponse:
        """Execute a chat completion request to the LLM."""
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "logprobs": False,
        }
        payload.update(kwargs)

        return self._execute("post", self.config.endpoint, json_data=payload)

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
