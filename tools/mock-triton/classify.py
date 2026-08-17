"""Deterministic stand-in for the chat-reports-classifier ONNX model.

The real model is a two-class sequence classifier: a tokenized chat message in
(with `token_type_ids`, since it is a BERT-family encoder that was trained on
pair input), two raw logits out — `logits` is [batch, 2] FP32, ordered
[not-a-report, report]. It is unbounded and un-softmaxed, as it is here; callers
softmax or threshold themselves.

Nothing here is trained, but the two properties dev code depends on hold:

  * **Deterministic.** The same token ids always produce the same logits, so a
    re-run classifies a message the same way every time.
  * **Both classes actually occur.** The score is the projection of the
    mean-pooled message onto one fixed direction in the same vector space
    `embed.py` builds, so roughly half of random inputs land on each side rather
    than everything collapsing to one label. Which side a given message lands on
    is arbitrary — there is no notion of "report" in here — but it is stable, and
    a message and its near-duplicate land together.

`token_type_ids` is accepted because the model takes it and the mock validates
what it declares, but a single message is all segment 0; nothing here reads it.
"""

from __future__ import annotations

import numpy as np

import embed

# The projection below is a cosine between two directions in embedding space, so it
# sits within ~1/sqrt(dim) of zero; `sqrt(dim)` rescales it to roughly unit
# variance, and this scale then spreads the logits over the few-units range a
# trained two-class head produces — some messages near 50/50, some near certain.
LOGIT_SCALE = 2.0 * float(np.sqrt(embed.EMBEDDING_DIM))

# The fixed decision direction. Drawn from the same generator as the token
# vectors, off a seed that is not any token id, so it is unrelated to every
# vector it is compared against.
_DIRECTION = np.random.default_rng(0xC1A55).standard_normal(embed.EMBEDDING_DIM, dtype=np.float32)
_DIRECTION /= np.linalg.norm(_DIRECTION)


def infer(
    input_ids: np.ndarray,
    attention_mask: np.ndarray,
    token_type_ids: np.ndarray,
) -> dict[str, np.ndarray]:
    """The model's single output for one batch.

    All three inputs are [batch, seq] INT64, exactly as the ONNX model takes
    them. Returns `logits` shaped [batch, 2] FP32.
    """
    batch = input_ids.shape[0]
    logits = np.empty((batch, 2), dtype=np.float32)

    for row in range(batch):
        tokens = input_ids[row][attention_mask[row].astype(bool)]
        if tokens.size == 0:
            logits[row] = 0.0
            continue

        pooled = np.stack([embed.vector_for(int(token)) for token in tokens]).mean(axis=0)
        norm = np.linalg.norm(pooled)
        # Pooling many unit vectors shrinks the norm towards zero, so project the
        # *direction* of the message: a long message is not automatically a
        # less confident one.
        score = 0.0 if norm == 0 else float(pooled @ _DIRECTION / norm)
        logits[row] = (-LOGIT_SCALE * score, LOGIT_SCALE * score)

    return {"logits": logits}
