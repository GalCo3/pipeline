# Agent Guide — tokenizers

`upload_tokenizer.py` puts a HuggingFace tokenizer into the object store so
`hermes.utils.triton.init_tokenizer` can pull it at runtime. Triton serves the
model; the tokenizer is not part of the model repository, so it travels
separately — this is that path.

## Layout contract

One flat prefix per tokenizer, no nesting:

```
s3://tokenizers/<name>/tokenizer.json
s3://tokenizers/<name>/tokenizer_config.json
s3://tokenizers/<name>/special_tokens_map.json
...
```

`init_tokenizer` lists `<name>/` and copies each object into
`<local_downloads_folder>/<name>/` by basename, then hands that directory to
`AutoTokenizer.from_pretrained`. The trailing slash on the prefix is what keeps
`bge-m3` from also matching `bge-m3-large`, and the download is only accepted
once a real tokenizer file lands — a half-written directory does not shadow the
next attempt.

Only tokenizer files go up (see `TOKENIZER_FILENAMES`). Model weights belong to
the Triton model repository, never here.

## Running it

```bash
export S3_ENDPOINT=http://localhost:9000
export S3_ACCESS_KEY=minioadmin S3_SECRET_KEY=minioadmin

uv run --with boto3 tools/scripts/tokenizers/upload_tokenizer.py \
    --source sentence-transformers/all-MiniLM-L6-v2 \
    --name all-MiniLM-L6-v2 --create-bucket
```

`--source` takes either a HuggingFace repo id or a directory that already holds
the files. The repo id form fetches over plain HTTPS (`<hub>/<repo>/resolve/main/<file>`),
so boto3 is the only dependency — no `transformers`, no `huggingface_hub`. A
404 per file is normal: a repo carries only the files its tokenizer type needs.

For the airgapped networks, split it in two: `--download-only DIR` on a
connected host, carry `DIR` over, then `--source DIR` there. `--dry-run` lists
what would be uploaded without touching S3. `--hub-url` (or `HF_ENDPOINT`)
points at a Hub mirror.

The tokenizer in use is `sentence-transformers/all-MiniLM-L6-v2` — WordPiece,
so it ships `tokenizer.json`, `tokenizer_config.json`, `vocab.txt` and
`special_tokens_map.json`, ~700KB total.

The local MinIO chart pre-creates the `tokenizers` bucket
(`helm-charts/local-infra/backing/minio`), so `--create-bucket` is only needed
against a store that does not have it yet.

Services then pass `--name` as `tokenizer_name_or_path` together with an
`s3_config`:

```python
TritonEmbedder(
    config=triton_config,
    model_name="all-MiniLM-L6-v2",
    s3_config=s3_config,
)
```
