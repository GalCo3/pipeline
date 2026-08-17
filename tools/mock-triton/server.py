"""Dev-only stand-in for the production Triton Inference Server.

Prod runs a real Triton (2.56.0) serving ONNX models on GPUs; the semantic
pipeline embeds chunks through its `retrieval_embedder` model, scores
query/document pairs through `cargo_reranker`, and labels chat messages through
`chat-reports-classifier`. Nothing in the local stack can run those — no GPU,
and the model files are not in this repo — so this serves the same KServe v2 API
over the same three ports, backed by `embed.py`, `rerank.py` and `classify.py`
instead of ONNX Runtime:

    8000  HTTP inference + health + metadata (`tritonclient.http`)
    8001  gRPC inference (`tritonclient.grpc`)
    8002  Prometheus metrics

Everything the server *says about itself* — server metadata, the repository
index, model metadata and model config — is replayed verbatim from the real
server; see contract.json. That is the point of the mock: dev code that reads
`max_batch_size`, tensor names or dtypes off the server gets prod's answers, and
the same code runs against both without branching.

What it deliberately keeps strict, because getting these wrong locally means
finding out in prod:

  * Every input is INT64 — the models take **token ids, not text**. There is no
    tokenizer in the model repository (raw onnxruntime_onnx, no ensemble, no
    python backend), so callers tokenize themselves, in dev exactly as in prod.
    Locally that tokenizer is sentence-transformers/all-MiniLM-L6-v2, served out
    of the `tokenizers` bucket by hermes.utils.triton.init_tokenizer — which is
    why the embedder here returns 384-d vectors, MiniLM's hidden size.
  * A batch over the model's `max_batch_size` (16 for the embedder and the
    reranker, 4 for the classifier) is rejected, with Triton's own message.
  * An unknown model, a missing input, or a dtype/shape mismatch is rejected.

What it does not model: real latency, GPU queueing, dynamic batching, shared
memory, and the `classification`/`trace`/`logging` extensions. They are listed
in the server metadata because prod lists them, but calling them 404s.
"""

from __future__ import annotations

import json
import logging
import threading
from concurrent import futures
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import classify
import embed
import grpc
import numpy as np
import rerank
from google.protobuf import json_format
from tritonclient.grpc import model_config_pb2, service_pb2, service_pb2_grpc

HTTP_PORT = 8000
GRPC_PORT = 8001
METRICS_PORT = 8002

CONTRACT = json.loads((Path(__file__).parent / "contract.json").read_text())
SERVER_METADATA = CONTRACT["server"]
REPOSITORY_INDEX = CONTRACT["repository_index"]
MODELS = CONTRACT["models"]

# The subset of the KServe dtype table these models use. Anything else is a
# request the real model would reject anyway.
NUMPY_DTYPES = {
    "BOOL": np.bool_,
    "INT8": np.int8,
    "INT16": np.int16,
    "INT32": np.int32,
    "INT64": np.int64,
    "UINT8": np.uint8,
    "UINT16": np.uint16,
    "UINT32": np.uint32,
    "UINT64": np.uint64,
    "FP16": np.float16,
    "FP32": np.float32,
    "FP64": np.float64,
}

# The stand-in behind each model in the contract. A contract entry with no
# implementation here is a bug, not a configuration: `_model_or_error` only lets
# through names that have metadata and config, and having those means the model
# claims to be READY.
IMPLEMENTATIONS = {
    "retrieval_embedder": embed.infer,
    "cargo_reranker": rerank.infer,
    "chat-reports-classifier": classify.infer,
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mock-triton")


class InferenceError(Exception):
    """A request Triton would reject: HTTP 400, gRPC INVALID_ARGUMENT."""


# Per-model success/failure counts, the two metrics anything in the local stack
# would actually graph. Real Triton exposes far more.
_stats_lock = threading.Lock()
_stats: dict[str, dict[str, int]] = {}


def _record(model: str, *, success: bool) -> None:
    # A request naming a model that does not exist is not that model's failure —
    # counting it would invent a metrics series (and a /stats entry) for a name
    # the server never served.
    if model not in MODELS:
        return
    with _stats_lock:
        counters = _stats.setdefault(model, {"success": 0, "fail": 0})
        counters["success" if success else "fail"] += 1


def _model_or_error(name: str) -> dict[str, Any]:
    """The contract entry for `name`, or Triton's own unknown-model error.

    A model listed in the repository index but not implemented here lands in the
    same branch on purpose — from a client's side it is indistinguishable from a
    model that failed to load, which is the honest answer.
    """
    model = MODELS.get(name)
    if model is None:
        raise InferenceError(f"Request for unknown model: '{name}' is not found")
    return model


def run_inference(model_name: str, inputs: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Validate one request against the model's config, then produce its outputs."""
    config = _model_or_error(model_name)["config"]

    expected = {spec["name"]: spec for spec in config["input"]}
    missing = sorted(set(expected) - set(inputs))
    if missing:
        raise InferenceError(
            f"expected {len(expected)} inputs but got {len(inputs)} inputs for model "
            f"'{model_name}', missing: {', '.join(missing)}"
        )

    for name, tensor in inputs.items():
        spec = expected.get(name)
        if spec is None:
            raise InferenceError(f"unexpected inference input '{name}' for model '{model_name}'")
        # config dtypes are the TYPE_ prefixed spelling; the wire uses the bare one.
        wanted = spec["data_type"].removeprefix("TYPE_")
        actual = next(k for k, v in NUMPY_DTYPES.items() if v == tensor.dtype.type)
        if actual != wanted:
            raise InferenceError(
                f"unexpected datatype {actual} for inference input '{name}', expecting {wanted}"
            )
        # max_batch_size > 0 means the config dims exclude the batch dimension,
        # so a [-1] input arrives on the wire as [batch, seq].
        if tensor.ndim != len(spec["dims"]) + 1:
            raise InferenceError(
                f"unexpected shape for input '{name}' for model '{model_name}': expected "
                f"{len(spec['dims']) + 1} dimensions, got {tensor.ndim}"
            )

    batch = next(iter(inputs.values())).shape[0]
    if batch > config["max_batch_size"]:
        raise InferenceError(
            f"inference request batch-size must be <= {config['max_batch_size']} for '{model_name}'"
        )

    # Every input these models take is one per token, so they arrive as parallel
    # [batch, seq] tensors. Ragged ones would be a caller bug the real model
    # notices only as a shape error deep in ONNX Runtime.
    reference_name, reference = next(iter(inputs.items()))
    for name, tensor in inputs.items():
        if tensor.shape != reference.shape:
            raise InferenceError(
                f"{name} shape {list(tensor.shape)} does not match {reference_name} shape "
                f"{list(reference.shape)}"
            )

    # Tensor names are the implementations' parameter names, so a model gaining
    # or losing an input is a contract.json edit plus a signature, nothing else.
    return IMPLEMENTATIONS[model_name](**inputs)


def _select_outputs(
    model_name: str, produced: dict[str, np.ndarray], requested: list[str] | None
) -> list[tuple[str, np.ndarray]]:
    """The outputs to return, in request order — or every output when none were asked for.

    Worth knowing when nothing is requested: `token_embeddings` is
    [batch, seq, 384] FP32, so a full 16 x 512 batch is 12 MB on the wire.
    Ask for `sentence_embedding` alone unless the token vectors are wanted.
    """
    if not requested:
        return [
            (spec["name"], produced[spec["name"]])
            for spec in MODELS[model_name]["metadata"]["outputs"]
        ]

    selected = []
    for name in requested:
        if name not in produced:
            raise InferenceError(f"unexpected inference output '{name}' for model '{model_name}'")
        selected.append((name, produced[name]))
    return selected


# ---------------------------------------------------------------------------
# HTTP (port 8000) — KServe v2 REST, including the binary tensor extension
# ---------------------------------------------------------------------------


class HTTPHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        log.info("http %s", format % args)

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_empty(self, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_error(self, message: str, status: int = 400) -> None:
        self._send_json({"error": message}, status)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/")
        parts = [segment for segment in path.split("/") if segment]

        try:
            # /v2/health/live, /v2/health/ready — 200 with an empty body, as Triton does.
            if parts[:2] == ["v2", "health"] and len(parts) == 3:
                self._send_empty()
                return

            if parts == ["v2"]:
                self._send_json(SERVER_METADATA)
                return

            if parts[:2] == ["v2", "models"] and len(parts) >= 3:
                name, trailing = _split_model_path(parts[2:])
                model = _model_or_error(name)

                if trailing == ["ready"]:
                    self._send_empty()
                    return
                if trailing == ["config"]:
                    self._send_json(model["config"])
                    return
                if trailing == ["stats"]:
                    self._send_json({"model_stats": [_model_stats(name)]})
                    return
                if not trailing:
                    self._send_json(model["metadata"])
                    return

            self._send_error(f"Not Found: {self.path}", 404)
        except InferenceError as error:
            self._send_error(str(error))

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/")
        parts = [segment for segment in path.split("/") if segment]

        try:
            if parts == ["v2", "repository", "index"]:
                self._send_json(REPOSITORY_INDEX)
                return

            if parts[:2] == ["v2", "models"] and len(parts) >= 3:
                name, trailing = _split_model_path(parts[2:])
                if trailing == ["infer"]:
                    self._handle_infer(name)
                    return

            self._send_error(f"Not Found: {self.path}", 404)
        except InferenceError as error:
            self._send_error(str(error))

    def _handle_infer(self, model_name: str) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))

        # Binary tensor extension: the JSON header is the first N bytes and every
        # tensor with a `binary_data_size` follows it, back to back, in order.
        header_length = self.headers.get("Inference-Header-Content-Length")
        if header_length is None:
            request, binary = json.loads(body), b""
        else:
            split = int(header_length)
            request, binary = json.loads(body[:split]), body[split:]

        inputs: dict[str, np.ndarray] = {}
        offset = 0
        for tensor in request.get("inputs", []):
            dtype = NUMPY_DTYPES.get(tensor["datatype"])
            if dtype is None:
                raise InferenceError(f"unsupported datatype {tensor['datatype']}")

            size = (tensor.get("parameters") or {}).get("binary_data_size")
            if size is None:
                array = np.asarray(tensor["data"], dtype=dtype).reshape(tensor["shape"])
            else:
                array = np.frombuffer(binary[offset : offset + size], dtype=dtype)
                array = array.reshape(tensor["shape"])
                offset += size
            inputs[tensor["name"]] = array

        try:
            produced = run_inference(model_name, inputs)
        except InferenceError:
            _record(model_name, success=False)
            raise
        _record(model_name, success=True)

        requested = [tensor["name"] for tensor in request.get("outputs", [])]
        # Whether an output comes back as JSON numbers or raw bytes is per-output
        # in the request; with no `outputs` at all, mirror how the inputs arrived.
        binary_by_name = {
            tensor["name"]: bool((tensor.get("parameters") or {}).get("binary_data", True))
            for tensor in request.get("outputs", [])
        }
        default_binary = header_length is not None

        response: dict[str, Any] = {
            "model_name": model_name,
            "model_version": MODELS[model_name]["metadata"]["versions"][0],
            "outputs": [],
        }
        if "id" in request:
            response["id"] = request["id"]

        payload = bytearray()
        for name, array in _select_outputs(model_name, produced, requested):
            entry: dict[str, Any] = {
                "name": name,
                "datatype": next(k for k, v in NUMPY_DTYPES.items() if v == array.dtype.type),
                "shape": list(array.shape),
            }
            if binary_by_name.get(name, default_binary):
                raw = array.tobytes()
                entry["parameters"] = {"binary_data_size": len(raw)}
                payload += raw
            else:
                entry["data"] = array.reshape(-1).tolist()
            response["outputs"].append(entry)

        header = json.dumps(response).encode()
        self.send_response(200)
        if payload:
            self.send_header("Inference-Header-Content-Length", str(len(header)))
            self.send_header("Content-Type", "application/octet-stream")
        else:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(header) + len(payload)))
        self.end_headers()
        self.wfile.write(header + bytes(payload))


def _split_model_path(parts: list[str]) -> tuple[str, list[str]]:
    """Strip an optional `/versions/<v>` out of a model path.

    `/v2/models/x/infer` and `/v2/models/x/versions/1/infer` are the same call —
    only version 1 exists, so the version is accepted and ignored.
    """
    name = parts[0]
    trailing = parts[1:]
    if trailing[:1] == ["versions"] and len(trailing) >= 2:
        trailing = trailing[2:]
    return name, trailing


def _model_stats(name: str) -> dict[str, Any]:
    with _stats_lock:
        counters = _stats.get(name, {"success": 0, "fail": 0})
    return {
        "name": name,
        "version": MODELS[name]["metadata"]["versions"][0],
        "inference_stats": {
            "success": {"count": counters["success"]},
            "fail": {"count": counters["fail"]},
        },
    }


# ---------------------------------------------------------------------------
# gRPC (port 8001)
# ---------------------------------------------------------------------------


class GRPCService(service_pb2_grpc.GRPCInferenceServiceServicer):
    """The same handlers as above, over the generated protobuf messages.

    The contract JSON is the protobuf JSON mapping of Triton's own messages —
    which is exactly what the HTTP endpoints return — so each response here is
    one `ParseDict` away, and the two protocols cannot drift apart.
    """

    def ServerLive(self, request, context):
        return service_pb2.ServerLiveResponse(live=True)

    def ServerReady(self, request, context):
        return service_pb2.ServerReadyResponse(ready=True)

    def ModelReady(self, request, context):
        return service_pb2.ModelReadyResponse(ready=request.name in MODELS)

    def ServerMetadata(self, request, context):
        return json_format.ParseDict(SERVER_METADATA, service_pb2.ServerMetadataResponse())

    def ModelMetadata(self, request, context):
        with _abort_on_error(context):
            model = _model_or_error(request.name)
        return json_format.ParseDict(model["metadata"], service_pb2.ModelMetadataResponse())

    def ModelConfig(self, request, context):
        with _abort_on_error(context):
            model = _model_or_error(request.name)
        return service_pb2.ModelConfigResponse(
            config=json_format.ParseDict(model["config"], model_config_pb2.ModelConfig())
        )

    def RepositoryIndex(self, request, context):
        return json_format.ParseDict(
            {"models": REPOSITORY_INDEX}, service_pb2.RepositoryIndexResponse()
        )

    def ModelStatistics(self, request, context):
        names = [request.name] if request.name else list(MODELS)
        return json_format.ParseDict(
            {"model_stats": [_model_stats(name) for name in names]},
            service_pb2.ModelStatisticsResponse(),
        )

    def ModelInfer(self, request, context):
        inputs: dict[str, np.ndarray] = {}
        for position, tensor in enumerate(request.inputs):
            dtype = NUMPY_DTYPES.get(tensor.datatype)
            if dtype is None:
                context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    f"unsupported datatype {tensor.datatype}",
                )
            # raw_input_contents is what tritonclient sends; the typed `contents`
            # field is the fallback for hand-built requests.
            if position < len(request.raw_input_contents):
                raw = request.raw_input_contents[position]
                array = np.frombuffer(raw, dtype=dtype).reshape(list(tensor.shape))
            else:
                flat = _typed_contents(tensor.contents, tensor.datatype)
                array = np.asarray(flat, dtype=dtype).reshape(list(tensor.shape))
            inputs[tensor.name] = array

        model_name = request.model_name
        try:
            produced = run_inference(model_name, inputs)
            requested = [tensor.name for tensor in request.outputs]
            selected = _select_outputs(model_name, produced, requested)
        except InferenceError as error:
            _record(model_name, success=False)
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(error))
        _record(model_name, success=True)

        response = service_pb2.ModelInferResponse(
            model_name=model_name,
            model_version=MODELS[model_name]["metadata"]["versions"][0],
            id=request.id,
        )
        for name, array in selected:
            response.outputs.append(
                service_pb2.ModelInferResponse.InferOutputTensor(
                    name=name,
                    datatype=next(k for k, v in NUMPY_DTYPES.items() if v == array.dtype.type),
                    shape=list(array.shape),
                )
            )
            response.raw_output_contents.append(array.tobytes())
        return response


def _typed_contents(contents, datatype: str) -> list[Any]:
    """Pull the populated repeated field out of an InferTensorContents."""
    field = {
        "BOOL": "bool_contents",
        "INT8": "int_contents",
        "INT16": "int_contents",
        "INT32": "int_contents",
        "INT64": "int64_contents",
        "UINT8": "uint_contents",
        "UINT16": "uint_contents",
        "UINT32": "uint_contents",
        "UINT64": "uint64_contents",
        "FP16": "fp32_contents",
        "FP32": "fp32_contents",
        "FP64": "fp64_contents",
    }[datatype]
    return list(getattr(contents, field))


class _abort_on_error:
    """Turns an InferenceError raised inside the block into a gRPC abort."""

    def __init__(self, context) -> None:
        self._context = context

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if isinstance(exc, InferenceError):
            self._context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return False


# ---------------------------------------------------------------------------
# Metrics (port 8002)
# ---------------------------------------------------------------------------


class MetricsHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Prometheus scrapes this every few seconds; logging it is noise.

    def do_GET(self) -> None:
        if self.path.rstrip("/") != "/metrics":
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        lines = [
            "# HELP nv_inference_request_success Number of successful inference requests",
            "# TYPE nv_inference_request_success counter",
            "# HELP nv_inference_request_failure Number of failed inference requests",
            "# TYPE nv_inference_request_failure counter",
        ]
        with _stats_lock:
            snapshot = {name: dict(counters) for name, counters in _stats.items()}
        for name, counters in snapshot.items():
            labels = f'model="{name}",version="1"'
            lines.append(f"nv_inference_request_success{{{labels}}} {counters['success']}")
            lines.append(f"nv_inference_request_failure{{{labels}}} {counters['fail']}")

        body = ("\n".join(lines) + "\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    service_pb2_grpc.add_GRPCInferenceServiceServicer_to_server(GRPCService(), grpc_server)
    grpc_server.add_insecure_port(f"[::]:{GRPC_PORT}")
    grpc_server.start()

    metrics = ThreadingHTTPServer(("", METRICS_PORT), MetricsHandler)
    threading.Thread(target=metrics.serve_forever, daemon=True).start()

    log.info(
        "mock triton %s serving http=%d grpc=%d metrics=%d models=%s",
        SERVER_METADATA["version"],
        HTTP_PORT,
        GRPC_PORT,
        METRICS_PORT,
        ", ".join(MODELS),
    )
    ThreadingHTTPServer(("", HTTP_PORT), HTTPHandler).serve_forever()


if __name__ == "__main__":
    main()
