from typing import Any

from hermes.text_extraction.config.settings import AppSettings


def create_settings(max_text_length: int = 100, **kwargs: Any) -> AppSettings:
    """Helper to instantiate AppSettings with a default tika_server_url for testing."""
    return AppSettings(
        max_text_length=max_text_length,
        tika_server_url="http://localhost:9998",  # type: ignore[arg-type]
        **kwargs,
    )
