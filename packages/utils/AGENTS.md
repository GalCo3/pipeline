# Agent Guide — Utils

Small, generic helpers shared across services that don't warrant their own package.
See the workspace-level [AGENTS.md](../../AGENTS.md) for shared tooling commands
(ruff/ty run from repo root).

## Structure

- `dls.py` — `DLSRecord` and `send_to_dls`, for writing failed Kafka messages to a
  Mongo-backed dead letter store.
- `site.py` — `site_error`, raises from a multi-site `(SiteResponse, SiteResponse | None)`
  pair (see `connections` `AGENTS.md`) if either side failed.

## Conventions

- Public API is re-exported from the package `__init__.py`; import from
  `hermes.utils` rather than reaching into submodules from other packages/services.
- Only add helpers here that are genuinely generic across services. Service-specific
  logic belongs in that service, not here.
