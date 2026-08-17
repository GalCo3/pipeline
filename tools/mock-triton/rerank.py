"""Deterministic stand-in for the cargo_reranker ONNX model.

The real model is a cross-encoder: one sequence holding a query and a candidate
document — `[CLS] query [SEP] document [SEP]` — in, one relevance logit out
(`logits`, [batch, 1] FP32). Higher is more relevant; the scale is unbounded and
uncalibrated, exactly as it is here.

Nothing here is trained, but the two properties dev code depends on hold:

  * **Deterministic.** The same token ids always produce the same logit, so a
    re-ranked result page is stable across re-runs.
  * **Ranking is meaningful-ish.** The score is the cosine similarity between
    the mean-pooled query half and the mean-pooled document half, using the same
    fixed per-token vectors as `embed.py`, scaled to a logit-looking range. A
    document sharing tokens with the query outranks one that shares none. It is
    *not* semantic: synonyms score like random words.

Splitting query from document is done by finding the separator token: in a
cross-encoder pair the last unmasked token is `[SEP]`, and that same id also
ends the query. When it appears only once (no pair encoded, or a tokenizer that
does not use `[SEP]`), there is nothing to compare halves of, so the whole
sequence is scored against itself — a constant-ish score, which is the honest
answer for an input that is not actually a pair.
"""

from __future__ import annotations

import embed
import numpy as np

# Cross-encoder logits for a trained reranker land roughly in [-10, 10]. Cosine
# is in [-1, 1], so this maps a full-overlap pair to ~8 and a disjoint one to ~0
# — separated enough that a dev-time threshold behaves like a prod one.
LOGIT_SCALE = 8.0


def _pooled(ids: np.ndarray) -> np.ndarray:
    """Mean of one segment's token vectors, or zeros when the segment is empty."""
    if ids.size == 0:
        return np.zeros(embed.EMBEDDING_DIM, dtype=np.float32)
    return np.stack([embed.vector_for(int(token)) for token in ids]).mean(axis=0)


def _split(ids: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Indices of the query tokens and the document tokens in one unmasked row.

    `ids` is the row with padding already stripped. The trailing token is the
    separator; its earlier occurrence, if any, is the query/document boundary.
    Leading `[CLS]` is dropped with the boundary token itself — neither carries
    content, and including a token both halves share would inflate every score.
    """
    if ids.shape[0] < 2:
        return ids, ids

    separator = ids[-1]
    (positions,) = np.nonzero(ids[:-1] == separator)
    if positions.size == 0:
        return ids, ids

    boundary = int(positions[0])
    return ids[1:boundary], ids[boundary + 1 : -1]


def infer(input_ids: np.ndarray, attention_mask: np.ndarray) -> dict[str, np.ndarray]:
    """The model's single output for one batch.

    `input_ids` and `attention_mask` are [batch, seq] INT64, exactly as the ONNX
    model takes them. Returns `logits` shaped [batch, 1] FP32.
    """
    batch = input_ids.shape[0]
    logits = np.empty((batch, 1), dtype=np.float32)

    for row in range(batch):
        unmasked = input_ids[row][attention_mask[row].astype(bool)]
        query, document = _split(unmasked)

        query_vector = _pooled(query)
        document_vector = _pooled(document)

        norms = np.linalg.norm(query_vector) * np.linalg.norm(document_vector)
        cosine = 0.0 if norms == 0 else float(query_vector @ document_vector / norms)
        logits[row, 0] = LOGIT_SCALE * cosine

    return {"logits": logits}
