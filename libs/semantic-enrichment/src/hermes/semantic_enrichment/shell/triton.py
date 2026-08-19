import numpy as np
import tritonclient.http as httpclient

from ..config_models.triton import TritonConfig


class BaseEmbeddingHandler:
    config: TritonConfig
    client: httpclient.InferenceServerClient

    def __init__(self, config: TritonConfig):
        self.config = config

        if not hasattr(self, "client"):
            self.client = httpclient.InferenceServerClient(
                url=config.url,
                network_timeout=config.timeout,
                connection_timeout=config.timeout,
            )

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        input_array = np.array([[text.encode("utf-8")] for text in texts], dtype=object)

        infer_input = httpclient.InferInput(self.config.input_name, input_array.shape, "BYTES")
        infer_input.set_data_from_numpy(input_array)

        output = httpclient.InferRequestedOutput(self.config.output_name)

        result = self.client.infer(
            model_name=self.config.model_name,
            model_version=self.config.model_version,
            inputs=[infer_input],
            outputs=[output],
        )

        return result.as_numpy(self.config.output_name).tolist()

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a batch of texts, chunking the request into `config.batch_size`-sized
        calls to Triton.

        :param texts: The texts to embed, in order.
        :return: One embedding vector per input text, in the same order.
        """
        if not texts:
            return []

        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self.config.batch_size):
            embeddings.extend(self._embed_batch(texts[start : start + self.config.batch_size]))

        return embeddings

    def close(self) -> None:
        self.client.close()
