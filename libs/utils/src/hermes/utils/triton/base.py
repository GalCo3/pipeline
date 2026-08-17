import logging
from pathlib import Path

import numpy as np
from transformers import AutoTokenizer

from hermes.connections.config_models.s3 import BaseS3Config
from hermes.connections.config_models.triton import BaseTritonConfig
from hermes.connections.handlers.s3 import BaseS3Handler
from hermes.connections.handlers.triton import BaseTritonHandler

logger = logging.getLogger(__name__)

# Standard NumPy to Triton REST API Datatype Mapping
NUMPY_TO_TRITON_DTYPE = {
    np.dtype("int64"): "INT64",
    np.dtype("int32"): "INT32",
    np.dtype("float32"): "FP32",
    np.dtype("float64"): "FP64",
    np.dtype("bool"): "BOOL",
}


# A directory only counts as a usable tokenizer once one of these is in it.
# An empty (or half-written) directory left behind by a failed download must
# not shadow a later attempt, which is why existence of the directory alone is
# never enough.
TOKENIZER_MARKER_FILES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
    "vocab.txt",
    "sentencepiece.bpe.model",
    "spiece.model",
)


def _is_tokenizer_dir(path: Path) -> bool:
    return any((path / name).is_file() for name in TOKENIZER_MARKER_FILES)


def _download_tokenizer_from_s3(
    s3_handler: BaseS3Handler,
    tokenizer_name: str,
    s3_bucket: str,
    destination: Path,
) -> bool:
    """
    Copies every object under `<tokenizer_name>/` into `destination`, flattened.

    The trailing slash matters: without it a prefix like `all-MiniLM-L6` also
    matches `all-MiniLM-L6-v2`, and the two would land in one directory.
    """
    prefix = f"{tokenizer_name.strip('/')}/"

    res, _ = s3_handler.list_files_by_prefix(prefix=prefix, bucket=s3_bucket)
    if not res.is_success:
        logger.warning("Listing s3://%s/%s failed: %s", s3_bucket, prefix, res.error)
        return False

    keys = [obj["Key"] for obj in res.response.get("Contents", []) if not obj["Key"].endswith("/")]
    if not keys:
        logger.warning("No tokenizer files under s3://%s/%s", s3_bucket, prefix)
        return False

    destination.mkdir(parents=True, exist_ok=True)
    for key in keys:
        file_resp, _ = s3_handler.get_file(key=key, bucket=s3_bucket)
        if not file_resp.is_success:
            logger.warning("Fetching s3://%s/%s failed: %s", s3_bucket, key, file_resp.error)
            continue
        (destination / Path(key).name).write_bytes(file_resp.response["Body"].read())

    return _is_tokenizer_dir(destination)


def init_tokenizer(
    tokenizer_name_or_path: str,
    s3_config: BaseS3Config | None = None,
    s3_bucket: str = "tokenizers",
    local_downloads_folder: str = "./downloaded_tokenizers",
):
    """
    Loads a HuggingFace tokenizer from a previous download, a local path, S3
    (via BaseS3Handler, when an S3 configuration is given), or the HuggingFace
    Hub — in that order.

    In S3 a tokenizer is one flat "directory" of objects keyed
    `<tokenizer_name>/<file>` in `s3_bucket`; the uploader that produces that
    layout is tools/scripts/tokenizers/upload_tokenizer.py.
    """
    local_tokenizer_path = Path(local_downloads_folder) / tokenizer_name_or_path

    if _is_tokenizer_dir(local_tokenizer_path):
        logger.info("Loading tokenizer from local download path: %s", local_tokenizer_path)
        return AutoTokenizer.from_pretrained(local_tokenizer_path)

    if Path(tokenizer_name_or_path).exists():
        logger.info("Loading tokenizer from specified path: %s", tokenizer_name_or_path)
        return AutoTokenizer.from_pretrained(tokenizer_name_or_path)

    if s3_config is not None:
        logger.info(
            "Downloading tokenizer '%s' from S3 bucket '%s'...",
            tokenizer_name_or_path,
            s3_bucket,
        )
        s3_handler = BaseS3Handler(s3_config)
        if _download_tokenizer_from_s3(
            s3_handler=s3_handler,
            tokenizer_name=tokenizer_name_or_path,
            s3_bucket=s3_bucket,
            destination=local_tokenizer_path,
        ):
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

        tokenizer_name = (
            tokenizer_name_or_path if tokenizer_name_or_path is not None else model_name
        )
        self.tokenizer = init_tokenizer(
            tokenizer_name_or_path=tokenizer_name,
            s3_config=s3_config,
            local_downloads_folder=local_downloads_folder,
        )
        self._accepted_inputs: set[str] | None = None

    def tokenize(self, text: str | list[str] | list[list[str]], **kwargs) -> dict[str, np.ndarray]:
        """Tokenizes input text into NumPy array dictionary."""
        return dict(
            self.tokenizer(text, padding=True, truncation=True, return_tensors="np", **kwargs)
        )

    def _drop_unaccepted_inputs(self, tokenized: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """
        Keeps only the tensors the served model declares as inputs.

        A tokenizer emits what its own architecture uses — a BERT one adds
        `token_type_ids` — while an exported model keeps only the inputs its
        graph reads. Triton rejects the whole request over one input it did not
        declare ("unexpected inference input"), so the extras are dropped here
        rather than surfacing as an inference failure.

        The model config is fetched once per instance; if that fetch fails,
        everything is sent and Triton stays the authority on what is valid.
        """
        if self._accepted_inputs is None:
            try:
                self._accepted_inputs = set(
                    self.triton_handler.get_model_input_dtypes(self.model_name, self.model_version)
                )
            except RuntimeError:
                logger.warning(
                    "Could not read the input list of '%s'; sending every tokenizer output",
                    self.model_name,
                )
                self._accepted_inputs = set()

        if not self._accepted_inputs:
            return tokenized

        dropped = sorted(set(tokenized) - self._accepted_inputs)
        if dropped:
            logger.debug("Model '%s' does not take %s", self.model_name, ", ".join(dropped))

        return {name: arr for name, arr in tokenized.items() if name in self._accepted_inputs}

    def _get_model_outputs(
        self, text_or_tokenized: str | list[str] | list[list[str]] | dict[str, np.ndarray]
    ) -> dict[str, np.ndarray]:
        """Queries Triton synchronously for model outputs."""
        tokenized_inputs = (
            self.tokenize(text_or_tokenized)
            if isinstance(text_or_tokenized, (str, list))
            else text_or_tokenized
        )
        tokenized_inputs = self._drop_unaccepted_inputs(tokenized_inputs)

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
