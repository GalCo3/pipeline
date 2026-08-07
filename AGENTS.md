# Agent Guide — Pipeline

This is a uv workspace. The root `pyproject.toml` is the workspace root and owns
the shared dev tooling config (`ruff`, `ty`); member packages do not repeat it.

## Layout

- `packages/` — Python libraries, published under the `hermes` namespace (`hermes.<package>`).
  - `connections/` — client factories/handlers for external services (Kafka, Mongo, Postgres, Elasticsearch, S3).
  - `text-extraction/` — functional-core/imperative-shell pipeline for extracting text from document streams.
  - `observability/` — structured logging, tracing, and metrics library.
- `services/` — deployable applications that consume the `packages/` libraries.
  - `cargo-lexical/` — placeholder service skeleton, not yet implemented.
- `helm-charts/` — Kubernetes deployment charts.

Each subdirectory with its own concerns has an `AGENTS.md`; read the nearest one
in the tree before making changes there. `CLAUDE.md` files are pointers only —
their content lives in the sibling `AGENTS.md`.

## Tooling (workspace-wide, configured once at root)

```bash
uv sync --all-packages     # install every workspace member into one .venv
uv run ruff check .        # lint (config: root pyproject.toml [tool.ruff])
uv run ruff format .       # format
uv run ty check            # type-check (config: root pyproject.toml [tool.ty])
```

Run these from the repo root — `ruff`/`ty` config is defined only in the root
`pyproject.toml` and applies to every package in the workspace. Do not add
`[tool.ruff]`/`[tool.ty]` sections to a package's own `pyproject.toml`.

Per-package commands (pytest, etc.) still run from inside that package's directory
since test config (`pythonpath`, fixtures) is package-specific.

## Conventions

- Package/service source lives under `<dir>/src/hermes/<name>/`; tests under `<dir>/tests/`.
- New packages must be added to `[tool.uv.workspace].members` in the root
  `pyproject.toml` (already globbed via `packages/*` and `services/*`, so a
  package just needs its own `pyproject.toml` to be picked up).
