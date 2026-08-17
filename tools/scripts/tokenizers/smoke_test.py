#!/usr/bin/env python3
"""
Drives the real Triton client against the local mock, with the real tokenizer.

This is the cheap half of the loop: no cluster, no MinIO, no images. It starts
`tools/mock-triton` in-process on its HTTP port and calls it through
`hermes.utils.triton`, so what it proves is the pairing — that the tokenizer in
the `tokenizers` bucket, the tensors the models declare, and the dimensions
downstream code indexes all agree. The S3 download path is the one thing it does
not cover; that needs the sandbox (see AGENTS.md next to this file).

    uv sync --all-packages
    uv run python tools/scripts/tokenizers/smoke_test.py

With no argument the tokenizer is fetched from the Hub into a temporary
directory. Pass a directory to use one already on disk (`--download-only` output,
or a copy carried into an airgapped network).
"""

import contextlib
import socket
import sys
import tempfile
import threading
import types
from http.server import ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TOKENIZER = "sentence-transformers/all-MiniLM-L6-v2"
EXPECTED_DIM = 384

sys.path[:0] = [
    str(REPO_ROOT / "tools" / "mock-triton"),
    str(REPO_ROOT / "tools" / "scripts" / "tokenizers"),
]


class _AnyMeta(type):
    def __getattr__(cls, name):
        return _Any


class _Any(metaclass=_AnyMeta):
    """Stands in for anything the stubbed modules are asked for."""

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return _Any()

    def __call__(self, *args, **kwargs):
        return _Any()


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        return _Any


def stub_tritonclient() -> None:
    """
    Fakes the tritonclient imports the mock makes for its gRPC surface.

    tritonclient ships only inside the mock's own image — it is there for the
    generated protobuf stubs, not to call anything — and this test speaks HTTP.
    grpc and protobuf are left real: the workspace venv has them.
    """
    for name in (
        "tritonclient",
        "tritonclient.grpc",
        "tritonclient.grpc.model_config_pb2",
        "tritonclient.grpc.service_pb2",
        "tritonclient.grpc.service_pb2_grpc",
    ):
        sys.modules.setdefault(name, _StubModule(name))


def free_port() -> int:
    with contextlib.closing(socket.socket()) as sock:
        sock.bind(("", 0))
        return sock.getsockname()[1]


def start_mock() -> int:
    """Serves the mock's HTTP API on a free port and returns it."""
    stub_tritonclient()
    import server

    httpd = ThreadingHTTPServer(("127.0.0.1", free_port()), server.HTTPHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd.server_address[1]


def resolve_tokenizer(argv: list[str], workdir: Path) -> str:
    if len(argv) > 1:
        return argv[1]

    from upload_tokenizer import HUB_URL, download_from_hub

    print(f"Fetching {TOKENIZER} into {workdir}")
    return str(download_from_hub(TOKENIZER, workdir, HUB_URL))


def check(label: str, actual, expected) -> bool:
    ok = actual == expected
    print(
        f"  {'PASS' if ok else 'FAIL'}  {label}: {actual}"
        + ("" if ok else f" (expected {expected})")
    )
    return ok


def main(argv: list[str]) -> int:
    port = start_mock()

    from hermes.connections.config_models.triton import BaseTritonConfig, BaseTritonSiteConfig
    from hermes.utils.triton import TritonEmbedder, TritonReranker

    config = BaseTritonConfig(local_site=BaseTritonSiteConfig(endpoint=f"http://127.0.0.1:{port}"))
    results = []

    with tempfile.TemporaryDirectory(prefix="smoke-tokenizer-") as tmp:
        tokenizer = resolve_tokenizer(argv, Path(tmp))

        with TritonEmbedder(
            config=config,
            model_name="retrieval_embedder",
            tokenizer_name_or_path=tokenizer,
        ) as embedder:
            declared = sorted(embedder.triton_handler.get_model_input_dtypes("retrieval_embedder"))
            emitted = sorted(embedder.tokenize("cargo manifest").keys())
            print(f"\nModel declares {declared}; tokenizer emits {emitted}")

            # The whole point of the input filter: a BERT tokenizer emits
            # token_type_ids that this model never declared, and Triton rejects
            # a request carrying an input it does not know.
            results.append(
                check("extra tokenizer outputs exist to drop", len(emitted) > len(declared), True)
            )

            pair = embedder.embed(["cargo manifest for the port", "port cargo manifest"])
            single = embedder.embed("cargo manifest for the port")
            unrelated = embedder.embed("zebra piano volcano")

            results.append(check("batch shape", pair.shape, (2, EXPECTED_DIM)))
            results.append(check("single shape", single.shape, (EXPECTED_DIM,)))
            results.append(check("unit norm", round(float((single**2).sum() ** 0.5), 3), 1.0))

            # Mock vectors are per-token random, so overlap ranking is the only
            # semantic property that holds — and the one dev code relies on.
            overlapping = float(pair[0] @ pair[1])
            disjoint = float(pair[0] @ unrelated)
            print(f"  cosine: overlapping {overlapping:.3f} vs unrelated {disjoint:.3f}")
            results.append(check("overlap ranks above unrelated", overlapping > disjoint, True))

        with TritonReranker(
            config=config,
            model_name="cargo_reranker",
            tokenizer_name_or_path=tokenizer,
        ) as reranker:
            scores = reranker.rerank("what ship", ["the cargo ship docked", "zebra piano volcano"])
            print(f"  rerank scores: {scores}")
            results.append(
                check("relevant document scores higher", bool(scores[0] > scores[1]), True)
            )

    failed = results.count(False)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
