"""Deterministic stand-in for the `text-embedding` model.

Unlike `retrieval_embedder`, which takes the token ids a caller tokenised
itself, this model takes raw UTF-8 text (a BYTES tensor) and returns one
1024-d vector per row — the shape `hermes.semantic_enrichment`'s
`BaseEmbeddingHandler` sends and expects, and the dimension the semantic index
mappings are built from.

The same two properties `embed.py` documents hold here, for the same reasons:

  * **Deterministic.** The same text always produces the same vector, so a
    re-run writes identical vectors to Elasticsearch and a query embedded
    twice matches itself exactly.
  * **Similarity is meaningful-ish.** Each word gets a fixed random unit
    vector and the row vector is their re-normalised mean, so two texts
    sharing words land closer together than two that share none. It is *not*
    semantic: synonyms are as far apart as random words.

Word order is ignored, which is what makes the overlap property hold. Nothing
downstream can tell, because only the pooled vector is indexed.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np

# Matches config.output[EMBEDDING].dims, every semantic index mapping's `dims`,
# and TRITON_CONFIG__EMBEDDING_DIM in the service charts — the one number in
# here that has to agree with anything else.
EMBEDDING_DIM = 1024

# Lowercased runs of word characters. Hebrew and other non-ASCII scripts are
# word characters to `re` under Unicode, so they tokenise the same way rather
# than collapsing into a single token.
_WORD = re.compile(r"\w+", re.UNICODE)

# word -> unit vector, filled on first sight, exactly like embed.py's per-token
# table: a dev run touches a small slice of any real vocabulary.
_VECTORS: dict[str, np.ndarray] = {}


def vector_for(word: str) -> np.ndarray:
    """The fixed unit vector for one word."""
    cached = _VECTORS.get(word)
    if cached is not None:
        return cached

    # Hash-seeded rather than seeded off the word itself, so near-identical
    # words do not give visibly correlated streams.
    digest = hashlib.blake2b(word.encode("utf-8"), digest_size=8).digest()
    rng = np.random.default_rng(int.from_bytes(digest, "big"))

    vector = rng.standard_normal(EMBEDDING_DIM, dtype=np.float32)
    vector /= np.linalg.norm(vector)
    _VECTORS[word] = vector
    return vector


def _embed_one(text: str) -> np.ndarray:
    words = _WORD.findall(text.lower())
    if not words:
        # An empty or punctuation-only row is not an error — the real model
        # returns a vector for it too. Zeros keep it orthogonal to everything
        # rather than accidentally close to some arbitrary word.
        return np.zeros(EMBEDDING_DIM, dtype=np.float32)

    pooled = np.mean([vector_for(word) for word in words], axis=0)
    norm = float(np.linalg.norm(pooled))
    # Vectors that cancel out leave a zero pooled vector, which has no
    # direction to normalise towards.
    return (pooled if norm == 0 else pooled / norm).astype(np.float32)


def infer(TEXT: np.ndarray) -> dict[str, np.ndarray]:  # noqa: N803 - Triton tensor name
    """One embedding per input row.

    `TEXT` is a [batch, 1] object array of UTF-8 bytes, which is how
    tritonclient puts a BYTES tensor on the wire. Returns [batch, 1024] FP32.
    """
    rows = []
    for value in TEXT.reshape(-1):
        text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
        rows.append(_embed_one(text))

    return {"EMBEDDING": np.stack(rows).astype(np.float32)}
