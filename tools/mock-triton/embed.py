"""Deterministic stand-in for the retrieval_embedder ONNX model.

The real model is a transformer: token ids in, one 1024-d vector per token
(`token_embeddings`) plus a mean-pooled, L2-normalised sentence vector
(`sentence_embedding`). Nothing here learns anything, but the two properties dev
code actually depends on hold:

  * **Deterministic.** The same token ids always produce the same vectors, so a
    re-run of the pipeline writes the same vectors to Elasticsearch and a
    query embedded twice matches itself exactly.
  * **Similarity is meaningful-ish.** Each token gets its own fixed random unit
    vector and the sentence vector is the mean-pooled, re-normalised sum of
    them, so two texts sharing tokens land closer together than two that share
    none. Cosine ranking in dev is therefore not pure noise — it ranks by token
    overlap. It is *not* semantic: synonyms are as far apart as random words.

Position is deliberately ignored (token 5 gets the same vector wherever it
appears). The real model is positional; nothing downstream can tell, because
only the pooled vector is indexed, and dropping position is what makes the
overlap property above hold.
"""

from __future__ import annotations

import hashlib

import numpy as np

# Matches config.output[sentence_embedding].dims — the one number in here that
# has to agree with contract.json, since the index mapping is built from it.
EMBEDDING_DIM = 1024

# token id -> unit vector, filled on first sight. A real vocabulary is ~30k-250k
# entries and a dev run touches a small slice of it, so building lazily beats
# materialising the whole table (250k x 1024 floats is a gigabyte).
_VECTORS: dict[int, np.ndarray] = {}


def vector_for(token_id: int) -> np.ndarray:
    """The fixed unit vector for one token id."""
    cached = _VECTORS.get(token_id)
    if cached is not None:
        return cached

    # Seeded off a hash of the id rather than the id itself: consecutive ids fed
    # straight to PCG64 give visibly correlated streams, which would make
    # neighbouring-token texts look artificially similar.
    digest = hashlib.blake2b(str(token_id).encode(), digest_size=8).digest()
    rng = np.random.default_rng(int.from_bytes(digest, "big"))

    vector = rng.standard_normal(EMBEDDING_DIM, dtype=np.float32)
    vector /= np.linalg.norm(vector)
    _VECTORS[token_id] = vector
    return vector


def _normalise(matrix: np.ndarray) -> np.ndarray:
    """Row-wise L2 normalisation, leaving all-zero rows alone."""
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    return matrix / np.where(norms == 0, 1.0, norms)


def infer(input_ids: np.ndarray, attention_mask: np.ndarray) -> dict[str, np.ndarray]:
    """Both model outputs for one batch.

    `input_ids` and `attention_mask` are [batch, seq] INT64, exactly as the ONNX
    model takes them. Returns FP32 arrays shaped [batch, seq, 1024] and
    [batch, 1024].
    """
    batch, seq = input_ids.shape

    token_embeddings = np.empty((batch, seq, EMBEDDING_DIM), dtype=np.float32)
    for row in range(batch):
        for position in range(seq):
            token_embeddings[row, position] = vector_for(int(input_ids[row, position]))

    # Mean pooling over the unmasked tokens, then re-normalise — what
    # sentence-transformers does, and the reason `attention_mask` is an input at
    # all. Padding tokens contribute nothing, so a padded batch gives the same
    # sentence vector as the same text sent on its own.
    mask = attention_mask.astype(np.float32)[..., None]
    masked = token_embeddings * mask
    counts = np.maximum(mask.sum(axis=1), 1.0)
    sentence_embedding = _normalise(masked.sum(axis=1) / counts).astype(np.float32)

    # Masked positions are zeroed in the token output too: the real model emits
    # *something* there, but anything reading padded positions is a bug, and
    # zeros make that bug loud instead of subtle.
    return {
        "token_embeddings": (token_embeddings * mask).astype(np.float32),
        "sentence_embedding": sentence_embedding,
    }
