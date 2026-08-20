import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..config_models.llm import BaseLLMConfig


def create_llm_session(config: BaseLLMConfig) -> requests.Session:
    """Create a configured requests Session for LLM interaction."""
    session = requests.Session()
    session.verify = config.verify_ssl
    session.headers.update(
        {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.token.strip()}",
        }
    )

    retry_strategy = Retry(
        total=config.max_retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session
