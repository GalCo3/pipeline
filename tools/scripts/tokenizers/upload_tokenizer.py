#!/usr/bin/env python3
"""
Upload a HuggingFace tokenizer into the S3/MinIO bucket that
`hermes.utils.triton.init_tokenizer` reads from.

The layout `init_tokenizer` expects is one flat prefix per tokenizer:

    s3://tokenizers/<name>/tokenizer.json
    s3://tokenizers/<name>/tokenizer_config.json
    ...

Source is either a directory that already holds the tokenizer files, or a
HuggingFace repo id. The repo id form fetches over plain HTTPS from the Hub —
no `transformers` or `huggingface_hub` needed, so this runs with nothing but
boto3 — but it does need Hub access, which the airgapped environments lack.
There the flow is two-step: `--download-only` on a connected host, carry the
directory over, then upload it with `--source <dir>`.

Usage:

    export S3_ENDPOINT=http://localhost:9000
    export S3_ACCESS_KEY=... S3_SECRET_KEY=...

    uv run --with boto3 tools/scripts/tokenizers/upload_tokenizer.py \\
        --source sentence-transformers/all-MiniLM-L6-v2 \\
        --name all-MiniLM-L6-v2 --create-bucket

`--name` defaults to the last path segment of `--source`, and is the string the
services then pass as `tokenizer_name_or_path`.
"""

import argparse
import logging
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

logger = logging.getLogger("upload-tokenizer")

# Only the tokenizer's own files go up — model weights are served by Triton and
# have no business in this bucket, and `from_pretrained` never reads them here.
TOKENIZER_FILENAMES = frozenset(
    {
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "added_tokens.json",
        "vocab.json",
        "vocab.txt",
        "merges.txt",
        "sentencepiece.bpe.model",
        "spiece.model",
        "source.spm",
        "target.spm",
        "chat_template.jinja",
    }
)

CONTENT_TYPES = {".json": "application/json", ".txt": "text/plain"}

HUB_URL = "https://huggingface.co"
HTTP_NOT_FOUND = 404


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--source", required=True, help="Local tokenizer directory or a HuggingFace repo id"
    )
    parser.add_argument("--name", help="Prefix to store under (default: last segment of --source)")
    parser.add_argument("--bucket", default=os.environ.get("S3_TOKENIZERS_BUCKET", "tokenizers"))
    parser.add_argument(
        "--endpoint", default=os.environ.get("S3_ENDPOINT", "http://localhost:9000")
    )
    parser.add_argument("--access-key", default=os.environ.get("S3_ACCESS_KEY"))
    parser.add_argument("--secret-key", default=os.environ.get("S3_SECRET_KEY"))
    parser.add_argument(
        "--create-bucket", action="store_true", help="Create the bucket if it is missing"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="List what would be uploaded and stop"
    )
    parser.add_argument(
        "--download-only",
        metavar="DIR",
        help="Fetch the tokenizer into DIR and stop, for carrying into an airgapped network",
    )
    parser.add_argument("--hub-url", default=os.environ.get("HF_ENDPOINT", HUB_URL))
    return parser.parse_args(argv)


def download_from_hub(repo_id: str, destination: Path, hub_url: str) -> Path:
    """
    Pulls the tokenizer files of `repo_id` into `destination` over HTTPS.

    A repo carries only some of TOKENIZER_FILENAMES — a WordPiece model has
    vocab.txt and no merges.txt, a sentencepiece one the reverse — so a 404 per
    file is expected and skipped; only ending up with nothing is an error.
    """
    destination.mkdir(parents=True, exist_ok=True)

    for filename in sorted(TOKENIZER_FILENAMES):
        url = f"{hub_url.rstrip('/')}/{repo_id}/resolve/main/{filename}"
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                (destination / filename).write_bytes(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code == HTTP_NOT_FOUND:
                continue
            raise
        logger.info("Fetched %s", url)

    return destination


def resolve_source(source: str, workdir: Path, hub_url: str) -> Path:
    """Returns a local directory holding the tokenizer files."""
    if Path(source).is_dir():
        return Path(source)

    logger.info("'%s' is not a directory — fetching it from the Hub", source)
    return download_from_hub(source, workdir, hub_url)


def collect_files(directory: Path) -> list[Path]:
    """Tokenizer files in `directory`, top level only — the layout is flat."""
    return sorted(
        entry
        for entry in directory.iterdir()
        if entry.name in TOKENIZER_FILENAMES and entry.is_file()
    )


def ensure_bucket(s3, bucket: str, create: bool) -> None:
    try:
        s3.head_bucket(Bucket=bucket)
        return
    except ClientError:
        if not create:
            raise
    s3.create_bucket(Bucket=bucket)
    logger.info("Created bucket %s", bucket)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    name = (args.name or args.source.rstrip("/").split("/")[-1]).strip("/")
    if not name:
        logger.error("Could not derive a tokenizer name from --source; pass --name")
        return 2

    if args.download_only:
        directory = resolve_source(args.source, Path(args.download_only), args.hub_url)
        files = collect_files(directory)
        if not files:
            logger.error("No tokenizer files found for %s", args.source)
            return 1
        logger.info("Wrote %d files to %s", len(files), directory)
        return 0

    with tempfile.TemporaryDirectory(prefix="tokenizer-") as tmp:
        directory = resolve_source(args.source, Path(tmp), args.hub_url)
        files = collect_files(directory)

        if not files:
            logger.error(
                "No tokenizer files found in %s (looked for %s)",
                directory,
                ", ".join(sorted(TOKENIZER_FILENAMES)),
            )
            return 1

        if args.dry_run:
            for path in files:
                logger.info("would upload s3://%s/%s/%s", args.bucket, name, path.name)
            return 0

        if not args.access_key or not args.secret_key:
            logger.error(
                "S3 credentials missing: set S3_ACCESS_KEY/S3_SECRET_KEY, "
                "or pass --access-key/--secret-key"
            )
            return 2

        s3 = boto3.client(
            "s3",
            endpoint_url=args.endpoint,
            aws_access_key_id=args.access_key,
            aws_secret_access_key=args.secret_key,
            config=Config(signature_version="s3v4"),
        )
        ensure_bucket(s3, args.bucket, args.create_bucket)

        for path in files:
            key = f"{name}/{path.name}"
            extra = {}
            content_type = CONTENT_TYPES.get(path.suffix)
            if content_type:
                extra["ContentType"] = content_type
            s3.put_object(Bucket=args.bucket, Key=key, Body=path.read_bytes(), **extra)
            logger.info("Uploaded s3://%s/%s", args.bucket, key)

    logger.info("Done. Services can now load it as tokenizer_name_or_path='%s'", name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
