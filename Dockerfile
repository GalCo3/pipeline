FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ARG SERVICE
ENV SERVICE=${SERVICE} \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Resolve dependencies from the manifests alone. Source edits do not touch
# these files, so this layer — and the wheel downloads behind it — survive
# a rebuild. `--no-install-workspace` skips the first-party packages, whose
# sources arrive in the next layer.
COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY services/ services/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package "${SERVICE}" --no-install-workspace

COPY . .

# Only the workspace packages are left to install; third-party wheels are
# already in place, and the shared cache covers anything the lock added.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package "${SERVICE}"

CMD ["sh", "-c", "exec uv run --frozen --no-dev --package \"$SERVICE\" python \"services/$SERVICE/main.py\""]
