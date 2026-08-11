from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class PayloadMode(Enum):
    BUFFER = "buffer"
    STREAM = "stream"


@dataclass(frozen=True)
class ExtractorSpec:
    fn: Callable[..., str]
    payload_mode: PayloadMode
    needs_tika_url: bool = False
