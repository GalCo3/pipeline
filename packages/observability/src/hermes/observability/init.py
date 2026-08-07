import logging
from typing import Any

from hermes.observability.core.setup_logging import configure_logging
from hermes.observability.core.setup_telemetry import configure_telemetry


def init_observability(
    service_name: str = "Telemetry-service",
    *,
    is_production: bool | None = None,
    log_level: int = logging.INFO,
    otlp_endpoint: str | None = None,
    enable_telemetry: bool = True,
) -> dict[str, Any]:
    """
    Global entrypoint to configure logging and OpenTelemetry telemetry in a single step.
    """
    configure_logging(is_production=is_production, log_level=log_level)

    if enable_telemetry:
        configure_telemetry(
            service_name=service_name,
            otlp_endpoint=otlp_endpoint,
            is_production=is_production,
        )

    return {
        "logging": True,
        "telemetry": enable_telemetry,
    }
