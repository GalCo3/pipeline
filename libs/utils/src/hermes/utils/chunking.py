import re
from collections.abc import Callable
from functools import cached_property

from llama_index.core.node_parser import SentenceSplitter

# Bump whenever chunking behaviour changes; stamped on every stored chunk.
CHUNKING_VERSION = "v2"

# In tokens of the embedding model's tokenizer, not words.
DEFAULT_CHUNK_SIZE_TOKENS = 512
DEFAULT_CHUNK_OVERLAP_TOKENS = 64

_REPEATED_DOTS = re.compile(r"(?:\.\s*){3,}")
_REPEATED_SPACES = re.compile(r"\s{2,}")


def preprocess_text(text: str) -> str:
    """Flatten the whitespace and dot runs extracted document text arrives with."""
    text = text.replace("\t", " ").replace("\n", " ")
    # The trailing space matters: the dot run may have eaten the one separating
    # it from the next sentence, splicing both into one unsplittable sentence.
    text = _REPEATED_DOTS.sub("... ", text)
    return _REPEATED_SPACES.sub(" ", text)


class SentenceChunker:
    """Splits text on sentence boundaries into token-bounded, overlapping chunks."""

    def __init__(
        self,
        tokenizer: Callable[[str], list],
        chunk_size: int = DEFAULT_CHUNK_SIZE_TOKENS,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP_TOKENS,
    ):
        """
        :param tokenizer: What to measure with — the `tokenize` method of the
            tokenizer of the model that will embed the chunks.
        :param chunk_size: Tokens per chunk.
        :param chunk_overlap: Tokens shared between consecutive chunks.
        """
        self.tokenizer = tokenizer
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @cached_property
    def splitter(self) -> SentenceSplitter:
        return SentenceSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            tokenizer=self.tokenizer,
        )

    def chunk_text(self, text: str) -> list[str]:
        """Split text into chunks, in order. Empty input yields an empty list."""
        cleaned = preprocess_text(text).strip()
        return self.splitter.split_text(cleaned) if cleaned else []
