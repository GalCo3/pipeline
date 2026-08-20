# Agent Guide — Utils

Small, generic helpers shared across services that don't warrant their own package.
See the workspace-level [AGENTS.md](../../AGENTS.md) for shared tooling commands
(ruff/ty run from repo root).

## Structure

- `dls.py` — `DLSRecord` and `send_to_dls`, for writing failed Kafka messages to a
  Mongo-backed dead letter store. Every service writes to the **one** `dls`
  collection; `source_topic` is what identifies the writer, since each service
  consumes its own topic. That collection is the read path of
  `apps/services/dls-console`, which groups, filters and replays from it.
  Per-service collections were tried and reverted — the triage UI is
  cross-service, so a split turns every listing into a `$unionWith` fan-out and
  makes the document identity `(collection, _id)` instead of `_id`.
- `dates.py` — `parse_date_value`, the single date entry point for every service's
  `field_validator`. Sources disagree (epoch millis, offset-bearing ISO, bare ISO), so it
  normalises to a **naive UTC** datetime at second resolution — every document then
  serialises as `yyyy-mm-ddThh:mm:ss`, which the `date` mappings accept as UTC under the
  default `strict_date_optional_time`. A bare input is read as UTC, not local time.
- `site.py` — `site_error`, raises from a multi-site `(SiteResponse, SiteResponse | None)`
  pair (see `connections` `AGENTS.md`) if either side failed.
- `indexing.py` — `with_indexed_at`, stamps a document with the time the pipeline handed
  it to Elasticsearch. Every service wraps its `index`/`update_by_id` body with it; the
  field must be declared in that index's mapping wherever `dynamic: strict` applies
  (see `apps/jobs/index-definitions`), so any further stamped field has to be added there too.
- `chunking.py` — `SentenceChunker`, the splitter every `*-semantic` service chunks
  with. It measures in **tokens of the embedding model's own tokenizer** (pass
  `init_tokenizer(...).tokenize`), not words, so a chunk that fits the limit also
  fits the model's input length, and it breaks on sentence boundaries via
  llama-index's `SentenceSplitter`. `preprocess_text` flattens the tabs, newlines
  and dot runs extracted document text arrives with before splitting.
  `CHUNKING_VERSION` identifies the algorithm; bump it whenever chunking behaviour
  changes so chunks produced under an old version stay identifiable.
- `triton/` — inference wrappers over `hermes.connections`' `BaseTritonHandler`:
  `TritonLM` (tokenize → infer → parse outputs, plus `model_tag` for stamping and
  `max_batch_size()` read off the served model), `TritonEmbedder`
  (`embed`/`embed_batched`), `TritonReranker`, `TritonTokenClassificationLM`, and
  `init_tokenizer`, which resolves a tokenizer from a local path, the `tokenizers`
  bucket or the HuggingFace Hub. The deployed Triton serves raw ONNX with no
  tokenizer of its own, so callers tokenize — that is why every wrapper here owns
  one, and why a service chunks with the same tokenizer it embeds with. This is
  the **only** Triton entry point for services; don't build a second client.
- `semantic.py` — shared between the `*-lexical`/`*-semantic` service pairs:
  `SemanticTriggerMessage`/`produce_semantic_trigger` for the lexical side to publish
  delete/update_metadata/index triggers, and `build_chunk_documents`/`replace_chunks`/
  `delete_chunks`/`diff_metadata_fields` for the semantic side to turn chunks+embeddings
  into indexed documents and decide whether a metadata change requires re-embedding.
  `fetch_lexical_document`/`fetch_first_chunk`/`denormalized_fields`/
  `chunk_and_embed_document`/`patch_chunk_metadata` are the semantic side's whole
  read-write flow: the two `*-semantic` services differ only in their indices,
  their text field and which fields stay off a chunk, so they pass those in rather
  than each keeping a copy of the flow. `SourceDocumentNotFoundError` is what
  `fetch_lexical_document` raises for a trigger whose lexical document is gone.
  Chunking (`chunking.py`) and embedding (`triton/`) live beside it — this module
  only orchestrates Elasticsearch writes around them.

## Conventions

- Public API is re-exported from the package `__init__.py`; import from
  `hermes.utils` rather than reaching into submodules from other packages/services.
- Only add helpers here that are genuinely generic across services. Service-specific
  logic belongs in that service, not here.
