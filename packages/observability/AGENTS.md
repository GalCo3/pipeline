# Agent Guide — Observability

Structured logging, tracing, and metrics library shared across services. See the
workspace-level [AGENTS.md](../../AGENTS.md) for shared tooling commands
(ruff/ty run from repo root).

## Structure

- `core/` — `setup_logging.py` (structlog configuration, `get_logger`), `setup_telemetry.py`
  (OpenTelemetry tracing/metrics setup), `circuit_breaker.py`.
- `logging/processors/` — structlog processors: `pii.py` (redaction), `source_info.py`,
  `event_level.py`, `trace_correlation.py` (log↔trace correlation), `explosion_guard.py`.
- `metrics/` — `TelemetryCounter`/`TelemetryGauge`/`TelemetryHistogram` wrappers, `guard.py`
  (label cleaning), `circuit_breaker.py`.
- `tracing/` — tracing-side circuit breaker.
- `utils/` — shared helpers: `context.py`, `environment.py`, `logging.py`, `network.py`, `queue.py`.
- `context.py` — `LogContext` and `bind_context`/`get_context`/`unbind_context`/`clear_context`
  for request/task-scoped structured log fields.
- `kafka.py` — `kafka_context` for correlating logs/traces across a consume/produce boundary.
- `fastapi.py` — `TelemetryFastAPIMiddleware` / `add_fastapi_observability` for wiring a FastAPI app.
- `task.py` — `instrument_task` decorator for background tasks.
- `init.py` — `init_observability`, the single entrypoint that wires logging + telemetry together.
- `constants.py`, `types.py` — shared constants (e.g. `DEFAULT_EXCLUDED_PATHS`) and enums
  (`CircuitBreakerState`, `MetricUnit`).

## Conventions

- Public API is re-exported from the package `__init__.py`; import from
  `hermes.observability` rather than reaching into submodules from other packages/services.
- `init_observability` is the intended single call site for wiring logging + telemetry in a
  service's entrypoint — prefer extending it over calling `configure_logging`/
  `configure_telemetry` separately from application code.
