# syntax=docker/dockerfile:1.7-labs
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder

ARG SERVICE
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY --parents libs/*/pyproject.toml apps/services/*/pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package "${SERVICE}" --no-install-workspace

COPY libs/ libs/
COPY apps/services/${SERVICE}/ apps/services/${SERVICE}/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package "${SERVICE}" --no-editable

RUN chgrp -R 0 /app && chmod -R g=u /app


FROM python:3.14-slim

ARG SERVICE
ENV SERVICE=${SERVICE} \
    HOME=/app \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/apps/services/${SERVICE} /app/apps/services/${SERVICE}

USER 1001

CMD ["sh", "-c", "exec python \"apps/services/$SERVICE/main.py\""]
