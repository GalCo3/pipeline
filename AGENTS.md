# Agent Guide — Pipeline

This is a uv workspace. The root `pyproject.toml` is the workspace root and owns
the shared dev tooling config (`ruff`, `ty`); member packages do not repeat it.

## Layout

- `libs/` — Python libraries, published under the `hermes` namespace (`hermes.<package>`).
  - `connections/` — client factories/handlers for external services (Kafka, Mongo, Postgres, Elasticsearch, S3).
  - `text-extraction/` — functional-core/imperative-shell pipeline for extracting text from document streams.
  - `observability/` — structured logging, tracing, and metrics library.
- `apps/services/` — deployable applications that consume the `libs/` libraries.
  - `cargo-lexical/` — placeholder service skeleton, not yet implemented.
  - `dls-console/` — the triage console: one Next.js app serving
    both the UI and its API over `hermes.dls`. Node, not Python, so it
    never joins the uv workspace; it ships its own `Dockerfile` and builds in
    Docker (no node toolchain on the host). See its `AGENTS.md`.
- `apps/jobs/` — one-off/batch applications that consume the `libs/` libraries.
  - `index-definitions/` — Elasticsearch index definition management.
- `helm-charts/` — Kubernetes deployment charts (`library/`, `services/`, `local-infra/`).
- `tools/` — things you run, not things you ship:
  - `scripts/sandbox/` — the local stack: `build-images.sh`, `install.sh`,
    `populate.sh`, `clean.sh`, `port-forward.sh`. They build images from the
    repo root and install every chart, which is why they sit here rather than
    under `helm-charts/`.
  - `scripts/image-registry/` — moving a built image between hosts:
    `export-image.sh`, `load_image.sh`.
  - `scripts/tokenizers/` — `upload_tokenizer.py`, which puts a HuggingFace
    tokenizer into the `tokenizers` bucket in the flat `<name>/<file>` layout
    `hermes.utils.triton.init_tokenizer` downloads from.
  - `demo-producer/` — dev-only Kafka/MinIO seeder image; its chart is
    `helm-charts/local-infra/tooling/demo-producer`.
  - `mock-triton/` — dev-only stand-in for the production Triton Inference
    Server, serving the KServe v2 API (HTTP, gRPC and metrics) with
    deterministic 384-d vectors instead of ONNX — 384 because locally every
    model tokenizes with all-MiniLM-L6-v2; its chart is
    `helm-charts/local-infra/backing/triton`.
  - `ci/` — CI helpers (`find_build.py`, called from `.gitlab-ci.yml`). It
    reads `uv.lock` to decide which apps a commit affects, and treats any
    directory under `apps/<group>/` with its own `Dockerfile` as an app too —
    that file overrides the shared `apps/Dockerfile`, which is how an app with a
    different entrypoint or a non-Python toolchain ships an image. Every image
    builds with the repo root as context.

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
  `pyproject.toml` (already globbed via `libs/*`, `apps/services/*`, and
  `apps/jobs/*`, so a package just needs its own `pyproject.toml` to be
  picked up).
