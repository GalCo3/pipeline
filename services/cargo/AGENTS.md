# Agent Guide — Cargo Service

Skeleton service, not yet implemented — `main.py` is an empty entrypoint and
`config.py` has an empty `CargoMessage(BaseModel)`. See the workspace-level
[AGENTS.md](../../AGENTS.md) for shared tooling commands.

This is a `uv` workspace member with `tool.uv.package = false` (it's an
application, not an importable library) — no `src/` layout needed here.
