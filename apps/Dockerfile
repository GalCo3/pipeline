# syntax=docker/dockerfile:1.7-labs
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder

ARG GROUP
ARG NAME
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY --parents libs/*/pyproject.toml apps/${GROUP}/*/pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package "${NAME}" --no-install-workspace

COPY libs/ libs/
COPY apps/${GROUP}/${NAME}/ apps/${GROUP}/${NAME}/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package "${NAME}" --no-editable

RUN chgrp -R 0 /app && chmod -R g=u /app


FROM python:3.14-slim

ARG GROUP
ARG NAME
ENV GROUP=${GROUP} \
    NAME=${NAME} \
    HOME=/app \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/apps/${GROUP}/${NAME} /app/apps/${GROUP}/${NAME}

USER 1001

CMD ["sh", "-c", "exec python \"apps/$GROUP/$NAME/main.py\""]
