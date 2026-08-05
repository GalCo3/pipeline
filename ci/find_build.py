"""Detect which services need a rebuild for the current commit range.

GitLab-runner-only: relies on CI_PROJECT_DIR/CI_COMMIT_BEFORE_SHA/CI_COMMIT_SHA,
which are only set inside a GitLab CI job.

A service is affected if either:
  - a file changed inside the service's own directory, or
  - a file changed inside a workspace package that the service depends on,
    directly or transitively (via `uv tree`, not by hand-parsing pyproject.toml,
    so multi-hop package -> package -> service chains are caught too).

Writes one line per affected service name to stdout, e.g.:

    cargo
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(os.environ["CI_PROJECT_DIR"])


def changed_files() -> set[Path] | None:
    """Returns None if there's no prior commit to diff against (first push to the repo)."""
    before = os.environ["CI_COMMIT_BEFORE_SHA"]
    after = os.environ["CI_COMMIT_SHA"]

    if set(before) == {"0"}:
        return None

    diff = subprocess.run(
        ["git", "diff", "--name-only", f"{before}..{after}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {Path(f) for f in diff.splitlines()}


def uv_tree(*, package: str | None = None) -> dict:
    cmd = ["uv", "tree", "--format", "json", "--frozen"]
    if package:
        cmd += ["--package", package]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def main() -> None:
    changed = changed_files()

    workspace = uv_tree()
    members = {
        m["name"]: Path(m["path"]).resolve().relative_to(REPO_ROOT) for m in workspace["members"]
    }
    services = {name: path for name, path in members.items() if path.parts[:1] == ("services",)}

    if changed is None:
        # No prior commit to diff against: can't tell what changed, so build everything.
        affected = sorted(services)
    else:
        changed_members = {
            name for name, path in members.items() if any(path in f.parents for f in changed)
        }
        affected = [
            name
            for name in sorted(services)
            if {m["name"] for m in uv_tree(package=name)["members"]} & changed_members
        ]

    for name in affected:
        print(name)


if __name__ == "__main__":
    sys.exit(main())
