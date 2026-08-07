import os


def normalize_endpoint(endpoint: str) -> str:
    """Removes schema prefix (e.g. http://) from gRPC endpoint if present."""
    if "://" in endpoint:
        return endpoint.split("://", 1)[1]
    return endpoint


def is_channel_insecure(endpoint: str, is_production: bool) -> bool:
    """Determines if the gRPC channel should be insecure (local dev / non-prod)."""
    return "localhost" in endpoint or "127.0.0.1" in endpoint or not is_production


def resolve_otlp_endpoint(otlp_endpoint: str | None = None) -> str:
    """Resolves and normalizes the OTLP endpoint from parameter, env, or default."""
    endpoint_val = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or "localhost:4317"
    return normalize_endpoint(endpoint_val)
