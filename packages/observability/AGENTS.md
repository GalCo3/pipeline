# Agent Guide — Observability

Placeholder package, not yet implemented — only a `pyproject.toml` exists so it
resolves as a `uv` workspace member (`tool.uv.package = false`, no `src/` yet).
See the workspace-level [AGENTS.md](../../AGENTS.md) for shared tooling commands.

When implementing this package, follow the same layout as the other packages:
source under `src/hermes/observability/`, tests under `tests/`, and flip
`tool.uv.package` back to a real build (`hatchling`, `packages = ["src/hermes"]`,
matching `packages/connections/pyproject.toml`) once there's code to ship.
