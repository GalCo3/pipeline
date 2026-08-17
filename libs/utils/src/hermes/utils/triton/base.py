import os
import logging
import numpy as np
from transformers import AutoTokenizer

from hermes.connections.config_models.triton import BaseTritonConfig
from hermes.connections.handlers.triton import BaseTritonHandler
from hermes.connections.config_models.s3 import BaseS3Config
from hermes.connections.handlers.s3 import BaseS3Handler

logger = logging.getLogger(__name__)

# Standard NumPy to Triton REST API Datatype Mapping
NUMPY_TO_TRITON_DTYPE = {
    np.dtype("int64"): "INT64",
    np.dtype("int32"): "INT32",
    np.dtype("float32"): "FP32",
    np.dtype("float64"): "FP64",
    np.dtype("bool"): "BOOL",
}


def init_tokenizer(
    tokenizer_name_or_path: str,
    s3_config: BaseS3Config | None = None,
    s3_bucket: str = "tokenizers",
    local_downloads_folder: str = "./downloaded_tokenizers",
):
    """
    Loads a HuggingFace tokenizer from local path, HuggingFace Hub,
    or downloads it from S3 via BaseS3Handler if an S3 configuration is provided.
    """
    local_tokenizer_path = os.path.join(local_downloads_folder, tokenizer_name_or_path)

    if os.path.exists(local_tokenizer_path):
        logger.info("Loading tokenizer from local download path: %s", local_tokenizer_path)
        return AutoTokenizer.from_pretrained(local_tokenizer_path)

    if os.path.exists(tokenizer_name_or_path):
        logger.info("Loading tokenizer from specified path: %s", tokenizer_name_or_path)
        return AutoTokenizer.from_pretrained(tokenizer_name_or_path)

    if s3_config is not None:
        logger.info("Downloading tokenizer '%s' from S3 bucket '%s'...", tokenizer_name_or_path, s3_bucket)
        os.makedirs(local_tokenizer_path, exist_ok=True)
        s3_handler = BaseS3Handler(s3_config)

        res, _ = s3_handler.list_files_by_prefix(prefix=tokenizer_name_or_path, bucket=s3_bucket)
        if res.is_success and "Contents" in res.response:
            for obj in res.response["Contents"]:
                key = obj["Key"]
                filename = os.path.basename(key)
                if not filename:
                    continue
                file_resp, _ = s3_handler.get_file(key=key, bucket=s3_bucket)
                if file_resp.is_success:
                    out_path = os.path.join(local_tokenizer_path, filename)
                    with open(out_path, "wb") as f:
                        f.write(file_resp.response["Body"].read())

        if os.path.exists(os.path.join(local_tokenizer_path, "tokenizer_config.json")) or os.path.exists(os.path.join(local_tokenizer_path, "vocab.json")):
            return AutoTokenizer.from_pretrained(local_tokenizer_path)

    logger.info("Loading tokenizer from HuggingFace Hub: %s", tokenizer_name_or_path)
    return AutoTokenizer.from_pretrained(tokenizer_name_or_path)


class TritonLM:
    """Base class for language model inference on Triton."""

    def __init__(
        self,
        config: BaseTritonConfig,
        model_name: str,
        model_version: str = "1",
        tokenizer_name_or_path: str | None = None,
        s3_config: BaseS3Config | None = None,
        local_downloads_folder: str = "./downloaded_tokenizers",
    ):
        self.triton_handler = BaseTritonHandler(config)
        self.model_name = model_name
        self.model_version = model_version

        tokenizer_name = tokenizer_name_or_path if tokenizer_name_or_path is not None else model_name
        self.tokenizer = init_tokenizer(
            tokenizer_name_or_path=tokenizer_name,
            s3_config=s3_config,
            local_downloads_folder=local_downloads_folder,
        )

    def tokenize(self, text: str | list[str] | list[list[str]], **kwargs) -> dict[str, np.ndarray]:
        """Tokenizes input text into NumPy array dictionary."""
        return dict(self.tokenizer(text, padding=True, truncation=True, return_tensors="np", **kwargs))

    def _get_model_outputs(
        self, text_or_tokenized: str | list[str] | list[list[str]] | dict[str, np.ndarray]
    ) -> dict[str, np.ndarray]:
        """Queries Triton synchronously for model outputs."""
        tokenized_inputs = (
            self.tokenize(text_or_tokenized)
            if isinstance(text_or_tokenized, (str, list))
            else text_or_tokenized
        )

        inputs = [
            {
                "name": name,
                "shape": list(arr.shape),
                "datatype": NUMPY_TO_TRITON_DTYPE.get(arr.dtype, "BYTES"),
                "data": arr.tolist(),
            }
            for name, arr in tokenized_inputs.items()
        ]

        local_resp, _ = self.triton_handler.infer(
            model_name=self.model_name,
            inputs=inputs,
            model_version=self.model_version,
        )

        if not local_resp.is_success:
            raise RuntimeError(f"Triton model inference failed: {local_resp.error}")

        return {
            out["name"]: np.array(out["data"]).reshape(out["shape"])
            if "shape" in out
            else np.array(out["data"])
            for out in local_resp.response.get("outputs", [])
        }

    def close(self):
        self.triton_handler.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
