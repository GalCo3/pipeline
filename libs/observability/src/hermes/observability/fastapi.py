import time
from collections.abc import Callable, Sequence
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars

from hermes.observability.constants import DEFAULT_EXCLUDED_PATHS
from hermes.observability.core.setup_logging import get_logger
from hermes.observability.utils import resolve_correlation_id


class TelemetryFastAPIMiddleware(BaseHTTPMiddleware):
    """Starlette/FastAPI Middleware for context clearing, correlation ID, and HTTP
    access logging."""

    def __init__(
        self,
        app: Any,
        *,
        excluded_paths: Sequence[str] | None = None,
        capture_headers: Sequence[str] | None = None,
        enable_access_logs: bool = True,
        enable_metrics: bool = True,
    ) -> None:
        super().__init__(app)
        self.excluded_paths = set(excluded_paths or DEFAULT_EXCLUDED_PATHS)
        self.capture_headers = [h.lower() for h in (capture_headers or [])]
        self.enable_access_logs = enable_access_logs
        self.enable_metrics = enable_metrics
        self.logger = get_logger("observability.fastapi")

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        clear_contextvars()
        start = time.perf_counter()

        cid = resolve_correlation_id(request.headers)
        path, method = request.url.path, request.method

        binds: dict[str, object] = {
            "correlation_id": cid,
            "http_method": method,
            "http_path": path,
        }
        for h in self.capture_headers:
            if val := request.headers.get(h):
                binds[f"header_{h.replace('-', '_')}"] = val
        bind_contextvars(**binds)

        is_logged = self.enable_access_logs and not any(
            path == p or path.startswith(p + "/") for p in self.excluded_paths
        )
        try:
            response: Response = await call_next(request)
            response.headers["X-Correlation-ID"] = cid
            if is_logged:
                duration = round(time.perf_counter() - start, 4)
                log_fn = (
                    self.logger.info
                    if response.status_code < HTTPStatus.BAD_REQUEST
                    else self.logger.warning
                )
                log_fn(
                    f"HTTP {method} {path} - {response.status_code}",
                    status_code=response.status_code,
                    duration_sec=duration,
                )
            return response
        except Exception as exc:
            if is_logged:
                duration = round(time.perf_counter() - start, 4)
                self.logger.error(
                    f"HTTP {method} {path} - 500 Internal Server Error",
                    status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                    duration_sec=duration,
                    error=str(exc),
                    exc_info=True,
                )
            raise


def add_fastapi_observability(
    app: FastAPI,
    *,
    excluded_paths: Sequence[str] | None = None,
    capture_headers: Sequence[str] | None = None,
    enable_access_logs: bool = True,
    enable_metrics: bool = True,
) -> None:
    """Registers Telemetry Observability middleware onto a FastAPI app."""
    app.add_middleware(
        TelemetryFastAPIMiddleware,
        excluded_paths=excluded_paths,
        capture_headers=capture_headers,
        enable_access_logs=enable_access_logs,
        enable_metrics=enable_metrics,
    )
    if enable_metrics:
        FastAPIInstrumentor().instrument_app(app)
