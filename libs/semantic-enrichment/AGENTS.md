# Agent Guide — Semantic Enrichment

Chunking and embedding building blocks shared by `cargo-semantic` and
`chief-semantic`. See the workspace-level [AGENTS.md](../../AGENTS.md) for
shared tooling commands (ruff/ty run from repo root).

## Structure

- `core/chunking.py` — pure, side-effect-free `chunk_text`. `CHUNKING_VERSION`
  identifies the algorithm; bump it whenever `chunk_text`'s behavior changes so
  chunks produced under an old version are identifiable.
- `config_models/triton.py` — `TritonConfig`, the only input the embedding
  handler accepts. `TritonConfig.embedding_version` identifies the deployed
  model/version a chunk's `embedding` came from, for the same reason as
  `CHUNKING_VERSION`.
- `shell/triton.py` — `BaseEmbeddingHandler`, a thin wrapper over
  `tritonclient.http` that batches embedding requests to `config.batch_size`.

## Conventions

- Keep `core/` free of I/O — no Triton client, no logging. Callers combine
  `chunk_text` and `BaseEmbeddingHandler` themselves.
- This library does not know about Elasticsearch or Kafka; it only turns text
  into chunks and chunks into vectors. Indexing/messaging stays in the
  consuming services.
