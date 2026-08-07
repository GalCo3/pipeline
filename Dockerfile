FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

# Which workspace member under services/ to build and run, e.g. "cargo-lexical".
ARG SERVICE
ENV SERVICE=${SERVICE} \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
COPY . .

RUN uv sync --frozen --no-dev --package "${SERVICE}"

CMD ["sh", "-c", "exec uv run --frozen --no-dev --package \"$SERVICE\" python \"services/$SERVICE/main.py\""]
