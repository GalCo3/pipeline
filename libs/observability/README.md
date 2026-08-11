# observability

Standardized Observability package for Telemetry microservices providing structured logging, context propagation, OpenTelemetry trace correlation, FastAPI middleware, Kafka ETL instrumentation, task decorators, and metrics.

## Key Features

- **Global Initialization**: `init_observability()` configures structured logging and OpenTelemetry OTLP exporters in one call.
- **Structured Logging**: Production JSON output or human-readable pretty console format with standardized timestamp and log level fields.
- **PII & Schema Protection**: Automatic redaction of sensitive credentials/PII (passwords, tokens, credit cards, SSNs) and root JSON schema mapping explosion protection.
- **Context Propagation**: Thread and coroutine-safe context binding (`bind_context`, `unbind_context`, `get_context`, `clear_context`) using `contextvars`.
- **OpenTelemetry Correlation**: Automatic injection of `trace_id`, `span_id`, and `parent_span_id` into log records when an OpenTelemetry span is active.
- **FastAPI Integration**: Middleware (`TelemetryFastAPIMiddleware` / `add_fastapi_observability`) for correlation ID propagation, response header injection, header capture, and health-check route filtering.
- **Kafka Integration**: Consumer-side correlation context extraction and metadata mapping using `kafka_context`.
- **Task Instrumentation**: Universal `@instrument_task` decorator for sync and async jobs with task parameter binding and duration measurement.
- **Developer Metrics Engine**: Built-in wrappers (`TelemetryCounter`, `TelemetryGauge`, `TelemetryHistogram`) with default explicit latency views, automatic High Cardinality checks, and OTel trace context binding for Exemplars support.

---

## Installation

Install using `uv`:

```bash
uv sync
```

---

## Quick Start Guide

### 1. Global Setup

Initialize logging and telemetry at host application startup:

```python
from hermes.observability import init_observability, get_logger

# Initialize observability (JSON format for production, OTLP telemetry exporter)
init_observability(
    service_name="order-service",
    is_production=True,
    log_level="INFO",
    otlp_endpoint="http://localhost:4317",
    enable_telemetry=True,
)

logger = get_logger("orders")
logger.info("Order service started")
```

### Configuration & Fallbacks

Both `init_observability` and the underlying configuration methods support automatic environment detection and fallbacks:

- **Production Environment (`is_production`)**: If not explicitly provided, the package detects the environment based on the host OS:
  - Resolves to `True` on Linux environments.
  - Resolves to `False` on non-Linux environments (e.g. Windows/macOS local dev machines).
- **OTLP Endpoint (`otlp_endpoint`)**: If not explicitly provided:
  - Looks up the standard `OTEL_EXPORTER_OTLP_ENDPOINT` environment variable.
  - Falls back to `localhost:4317` if the environment variable is not defined.

### 2. Context Binding & PII Protection

```python
from hermes.observability import bind_context, clear_context, LogContext, get_logger

logger = get_logger("checkout")

# Bind context globally across async tasks
bind_context(tenant_id="acme_corp", env="production")

# Sensitive data is automatically redacted by pii_redactor
logger.info("User checkout initiated", password="my_secret_password")

# Scoped block context manager
with LogContext(name="payment_processing", order_id="ord_9981"):
    logger.info("Executing payment provider call")

clear_context()
```

### 3. FastAPI Middleware

```python
from fastapi import FastAPI
from hermes.observability import add_fastapi_observability, init_observability

app = FastAPI()
init_observability(service_name="payment-api")

# Add middleware for correlation tracking and header capture
add_fastapi_observability(
    app,
    capture_headers=["x-request-id", "user-agent"],
    excluded_paths=["/healthz", "/metrics"],
)
```

### 4. Kafka Consumer Integration

```python
from hermes.observability import (
    kafka_context,
    get_logger,
)

logger = get_logger("kafka_worker")

# Consumer: Extract correlation headers and bind message coordinates
with kafka_context(msg, name="process_order_event"):
    logger.info("Processing order event from Kafka")
```

### 5. Task & Cron Instrumentation

```python
from hermes.observability import instrument_task, get_logger

logger = get_logger("cron")


@instrument_task(name="daily_report_generation", bind_args=True)
def generate_report(report_type: str):
    logger.info("Generating daily report")
```

### 6. Developer Metric Wrappers (Counter, Gauge, Histogram)

```python
from hermes.observability import TelemetryCounter, TelemetryGauge, TelemetryHistogram

# Counter with whitelist label keys
request_counter = TelemetryCounter("http_requests_processed_total", allowed_labels=["method"])
request_counter.inc(labels={"method": "GET"})

# Gauge with delta tracking
active_jobs_gauge = TelemetryGauge("active_jobs_count", allowed_labels=["queue"])
active_jobs_gauge.set(5.0, labels={"queue": "default"})

# Histogram with timed context manager
duration_hist = TelemetryHistogram("job_duration_seconds", allowed_labels=["job_name"])
with duration_hist.time(labels={"job_name": "backup"}):
    # Perform timed operation
    pass
```

---

## Comprehensive Runnable Examples

To see all features in action, run the included example scripts:

```bash
# Run logging and context manager examples
uv run python examples/logging_usage.py

# Run metric wrappers and high cardinality guard examples
uv run python examples/observability_features_usage.py
```

---

## Running Tests

Verify library functionality, type safety, and linting:

```bash
# Run unit & integration tests
.venv/Scripts/pytest

# Run type checker
.venv/Scripts/mypy src

# Run linter
.venv/Scripts/ruff check src
```
