# Agent Guide — Connections

Client factories and handlers for external services used across the pipeline:
Kafka, MongoDB, PostgreSQL, Elasticsearch, S3. See the workspace-level
[AGENTS.md](../../AGENTS.md) for shared tooling commands (ruff/ty run from repo root).

## Structure

- `config_models/` — Pydantic settings per backend (`kafka.py`, `mongo.py`, `postgres.py`,
  `elastic.py`, `s3.py`, `ssl.py`). These are the only inputs factories/handlers accept.
- `factories/` — pure construction functions that turn a config model into a raw client
  (e.g. `create_postgres_connection_pool`, `create_mongo_clients`). No app-specific logic.
- `handlers/` — wrap raw clients with the application-facing API (`BaseMongoHandler`,
  `BaseMongoHandler.find_one`, etc.). This is where retry/error-shaping logic belongs.
- `contexts/` — context managers for connection lifecycle (e.g. `contexts/postgres.py`).
- `serialization/` — wire-format helpers (Avro, etc.) for Kafka producers/consumers.
- `models.py` — shared response types, e.g. `SiteResponse(is_success, error, response)`.
- `exceptions.py` — package-specific exceptions (`S3Error`, `KafkaDeliveryError`,
  `ProducerSchemaError` and subclasses).

## Conventions

- Keep the factory/handler split: factories build clients from config, handlers add
  behavior. Don't put I/O-building logic in a handler or app logic in a factory.
- Handlers that support multi-site/local+remote operation return
  `tuple[SiteResponse, SiteResponse | None]` (local, remote) — follow this pattern
  for new handler methods rather than raising directly, so callers can inspect
  partial failures across sites.
- Auth on config models is a union (e.g. `str | SSL`) — factories branch on
  `isinstance(config.auth, ...)`; extend that branch rather than adding new
  parallel functions when adding an auth mode.
