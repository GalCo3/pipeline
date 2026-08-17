CHUNKING_VERSION = "v1"

DEFAULT_CHUNK_SIZE_WORDS = 220
DEFAULT_CHUNK_OVERLAP_WORDS = 40


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE_WORDS,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP_WORDS,
) -> list[str]:
    """
    Split text into overlapping, word-bounded chunks.

    :param text: The text to split.
    :param chunk_size: Words per chunk.
    :param chunk_overlap: Words shared between consecutive chunks.
    :return: Ordered list of chunk strings. Empty input yields an empty list.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    words = text.split()
    if not words:
        return []

    step = chunk_size - chunk_overlap
    return [" ".join(words[start : start + chunk_size]) for start in range(0, len(words), step)]
