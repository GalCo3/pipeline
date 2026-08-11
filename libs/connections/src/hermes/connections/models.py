from dataclasses import dataclass
from typing import Any


@dataclass
class SiteResponse:
    """Represents a connection response"""

    is_success: bool
    error: Exception | str | None = None
    response: Any | None = None
