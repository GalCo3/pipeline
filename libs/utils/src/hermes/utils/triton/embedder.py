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

    def embed_batched(self, texts: list[str], batch_size: int | None = None) -> list[list[float]]:
        """
        Embed many texts as several requests the served model accepts.

        Every row of one request is padded to the longest sequence in it, so
        batching also keeps one long text from padding out an entire corpus.

        :param texts: The texts to embed, in order.
        :param batch_size: Rows per request; defaults to the model's own
            `max_batch_size`, and 0 sends everything in one request.
        :return: One embedding vector per input text, in the same order.
        """
        if not texts:
            return []

        step = self.max_batch_size() if batch_size is None else batch_size
        if step <= 0:
            return self.embed(texts).tolist()

        return [
            embedding
            for start in range(0, len(texts), step)
            for embedding in self.embed(texts[start : start + step]).tolist()
        ]
