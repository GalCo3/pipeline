import numpy as np

from .base import TritonLM


def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    """Computes softmax scores along a given axis."""
    e_x = np.exp(x - np.max(x, axis=axis, keepdims=True))
    return e_x / e_x.sum(axis=axis, keepdims=True)


class TritonTokenClassificationLM(TritonLM):
    """Token classification language model wrapper for Triton."""

    def classify(self, text: str | list[str]) -> tuple[np.ndarray, np.ndarray]:
        """Classifies text token-by-token. Returns (label_ids, confidence_scores)."""
        parsed_model_output = self._get_model_outputs(text_or_tokenized=text)
        scores_np = softmax(parsed_model_output["logits"], axis=-1)

        label_ids = np.argmax(scores_np, axis=-1)
        label_scores = np.max(scores_np, axis=-1)

        return label_ids, label_scores
