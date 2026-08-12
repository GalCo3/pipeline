# Agent Guide — Utils

Small, generic helpers shared across services that don't warrant their own package.
See the workspace-level [AGENTS.md](../../AGENTS.md) for shared tooling commands
(ruff/ty run from repo root).

## Structure

- `dls.py` — `DLSRecord` and `send_to_dls`, for writing failed Kafka messages to a
  Mongo-backed dead letter store. Every service writes to the **one** `dls`
  collection; `source_topic` is what identifies the writer, since each service
  consumes its own topic. That collection is the read path of
  `apps/services/dls-portal`, which groups, filters and replays from it.
  Per-service collections were tried and reverted — the triage UI is
  cross-service, so a split turns every listing into a `$unionWith` fan-out and
  makes the document identity `(collection, _id)` instead of `_id`.
- `site.py` — `site_error`, raises from a multi-site `(SiteResponse, SiteResponse | None)`
  pair (see `connections` `AGENTS.md`) if either side failed.
- `indexing.py` — `with_indexed_at`, stamps a document with the time the pipeline handed
  it to Elasticsearch. Every service wraps its `index`/`update_by_id` body with it; the
  field must be declared in that index's mapping wherever `dynamic: strict` applies
  (see `apps/jobs/index-definitions`), so any further stamped field has to be added there too.

## Conventions

- Public API is re-exported from the package `__init__.py`; import from
  `hermes.utils` rather than reaching into submodules from other packages/services.
- Only add helpers here that are genuinely generic across services. Service-specific
  logic belongs in that service, not here.
