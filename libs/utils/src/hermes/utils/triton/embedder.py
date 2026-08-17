import numpy as np

from .base import TritonLM


class TritonEmbedder(TritonLM):
    """Embedding model wrapper for Triton."""

    def embed(self, text: str | list[str], get_token_embeddings: bool = False) -> np.ndarray:
        """Embeds text into dense vectors."""
        parsed_model_output = self._get_model_outputs(text_or_tokenized=text)

        target_key = "token_embeddings" if get_token_embeddings else "sentence_embedding"
        output = parsed_model_output[target_key]

        return output.squeeze(axis=0) if isinstance(text, str) else output
