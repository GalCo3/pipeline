import numpy as np
from .base import TritonLM


class TritonCrossEncoder(TritonLM):
    """Cross-encoder model wrapper for pairwise text scoring."""

    def predict(self, pairs: list[list[str]]) -> np.ndarray:
        """Predicts similarity scores for text pairs."""
        parsed_model_output = self._get_model_outputs(text_or_tokenized=pairs)
        logits = parsed_model_output.get("logits", parsed_model_output.get("scores"))

        return logits.squeeze() if logits is not None else parsed_model_output


class TritonReranker(TritonCrossEncoder):
    """Reranker wrapper for ordering document lists against a query."""

    def rerank(self, query: str, documents: list[str]) -> np.ndarray:
        """Reranks documents given a search query."""
        pairs = [[query, doc] for doc in documents]
        return self.predict(pairs)
