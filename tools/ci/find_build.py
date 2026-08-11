"""Detect which apps need a rebuild for the current commit range.

GitLab-runner-only: relies on CI_PROJECT_DIR/CI_COMMIT_BEFORE_SHA/CI_COMMIT_SHA,
which are only set inside a GitLab CI job.

An app is affected if either:
  - a file changed inside the app's own directory, or
  - a file changed inside a workspace package that the app depends on,
    directly or transitively (via `uv tree`, not by hand-parsing pyproject.toml,
    so multi-hop package -> package -> app chains are caught too).

Changes that cannot alter what the image does at runtime are ignored, so a
doc edit in a shared package does not fan out into a rebuild of every app
that depends on it.

Writes one "<group>/<name>" line per affected app to stdout, e.g.:

    services/cargo-lexical
    jobs/index-definitions
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(os.environ["CI_PROJECT_DIR"])

# Every app is built from the same shared Dockerfile.
DOCKERFILE = Path("apps/Dockerfile")
GROUPS = ("services", "jobs")

# Files the image may well contain — the Dockerfile copies whole package
# directories — but which nothing at runtime reads. Editing one of these in a
# shared package would otherwise rebuild every app that depends on it.
IGNORED_SUFFIXES = {".md"}
IGNORED_NAMES = {".gitignore", ".gitattributes"}


def is_ignored(path: Path) -> bool:
    return path.suffix in IGNORED_SUFFIXES or path.name in IGNORED_NAMES


def changed_files() -> set[Path] | None:
    """Returns None if there's no prior commit to diff against (first push to the repo).

    An empty set means every changed file was ignorable, which is not the same
    thing: nothing needs building.
    """
    before = os.environ["CI_COMMIT_BEFORE_SHA"]
    after = os.environ["CI_COMMIT_SHA"]

    if set(before) == {"0"}:
        return None

    diff = subprocess.run(
        ["git", "diff", "--name-only", f"{before}..{after}"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout
    return {path for f in diff.splitlines() if not is_ignored(path := Path(f))}


def uv_tree(*, package: str | None = None) -> dict:
    cmd = ["uv", "tree", "--format", "json", "--frozen"]
    if package:
        cmd += ["--package", package]
    result = subprocess.run(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, text=True, check=True)
    return json.loads(result.stdout)


def main() -> None:
    changed = changed_files()

    workspace = uv_tree()
    members = {
        m["name"]: Path(m["path"]).resolve().relative_to(REPO_ROOT) for m in workspace["members"]
    }

    affected: list[str] = []
    for group in GROUPS:
        group_members = {
            name: path for name, path in members.items() if path.parts[:2] == ("apps", group)
        }

        if changed is None or DOCKERFILE in changed:
            # No prior commit to diff against, or the shared Dockerfile
            # changed (every app is built from it): build everything.
            group_affected = sorted(group_members)
        elif not changed:
            # Everything in the range was ignorable (docs and the like).
            group_affected = []
        else:
            changed_members = {
                name for name, path in members.items() if any(path in f.parents for f in changed)
            }
            group_affected = [
                name
                for name in sorted(group_members)
                if {m["name"] for m in uv_tree(package=name)["members"]} & changed_members
            ]

        affected.extend(f"{group}/{name}" for name in group_affected)

    for entry in affected:
        print(entry)


if __name__ == "__main__":
    sys.exit(main())
