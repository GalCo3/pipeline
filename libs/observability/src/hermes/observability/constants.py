from typing import Final

# Noisy third-party libraries to suppress in production
NOISY_LOGGERS: Final[list[str]] = [
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "gunicorn",
    "gunicorn.error",
    "gunicorn.access",
    "boto3",
    "botocore",
    "urllib3",
    "httpx",
    "httpcore",
    "kafka",
    "aiokafka",
]

# Packages whose internal stack frames should be ignored by the callsite tracker
IGNORED_PACKAGES: Final[list[str]] = ["observability"]

# Whitelisted root JSON keys allowed in the log output root
WHITELISTED_KEYS: Final[set[str]] = {
    "timestamp",
    "level",
    "message",
    "logger",
    "trace_id",
    "span_id",
    "parent_span_id",
    "service_name",
    "correlation_id",
    "source",
    "exception",
    "stack_info",
    "exc_info",
    "metadata",
}

# Key substrings considered sensitive and targeted for redaction
SENSITIVE_KEY_SUBSTRINGS: Final[set[str]] = {
    "password",
    "secret",
    "token",
    "credit_card",
    "creditcard",
    "authorization",
    "cvv",
    "ssn",
    "passwd",
    "api_key",
    "apikey",
}

# Default latency boundaries (in seconds) for metrics histograms
DEFAULT_HISTOGRAM_BOUNDARIES: Final[list[float]] = [
    0.005,
    0.01,
    0.025,
    0.05,
    0.075,
    0.1,
    0.25,
    0.5,
    0.75,
    1.0,
    2.5,
    5.0,
    7.5,
    10.0,
]

# Bounded queue threshold (85%) above which telemetry data is dropped to prevent OOM
QUEUE_DROP_THRESHOLD: Final[float] = 0.85

# Keys that traditionally contain high-cardinality values and should be redacted in metrics
HIGH_CARDINALITY_KEYS: Final[set[str]] = {
    "user_id",
    "email",
    "uuid",
    "task_id",
    "transaction_id",
    "order_id",
    "correlation_id",
    "request_id",
}

DEFAULT_EXCLUDED_PATHS: Final[set[str]] = {
    "/health",
    "/ready",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/favicon.ico",
    "/static",
}

# Default string encoding
DEFAULT_ENCODING: Final[str] = "utf-8"
