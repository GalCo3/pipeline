"""Detect which apps need a rebuild for the current commit range.

GitLab-runner-only: relies on CI_PROJECT_DIR/CI_COMMIT_BEFORE_SHA/CI_COMMIT_SHA,
which are only set inside a GitLab CI job.

An app is a uv workspace member under `apps/<group>/`, or any directory under it
that carries its own `Dockerfile`. The second case is what lets a non-Python app
(or one that is not a workspace member) ship an image: `apps/services/dls-console/`
is a Node app that never joins the workspace.

An app is affected if either:
  - a file changed inside the app's own directory, or
  - a file changed inside a workspace package that the app depends on,
    directly or transitively (walked from uv.lock, so multi-hop
    package -> package -> app chains are caught too). Non-member apps have no
    such dependencies — only their own directory counts.

Changes that cannot alter what the image does at runtime are ignored, so a
doc edit in a shared package does not fan out into a rebuild of every app
that depends on it.

Writes one "<group> <image-name> <path>" line per affected app to stdout:

    services cargo-lexical apps/services/cargo-lexical
    services dls-console apps/services/dls-console
    jobs index-definitions apps/jobs/index-definitions

The image name is the app's path below its group with "/" replaced by "-", so a
nested app cannot collide with a top-level one.
"""

import os
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(os.environ["CI_PROJECT_DIR"])

# The workspace graph is read straight out of uv.lock rather than from
# `uv tree`: the lockfile is the same source of truth, needs no resolver run,
# and does not depend on a uv CLI flag staying put (`uv tree --format json`,
# used here before, no longer exists).
LOCKFILE = "uv.lock"

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


def workspace_graph() -> tuple[dict[str, Path], dict[str, set[str]]]:
    """({member name: path}, {member name: the members it depends on directly}).

    A workspace member is a locked package whose source is a local path —
    `editable` for a real package, `virtual` for one with `package = false`.
    The root project ("." ) is not an app and is dropped.
    """
    lock = tomllib.loads((REPO_ROOT / LOCKFILE).read_text())

    paths: dict[str, Path] = {}
    for pkg in lock["package"]:
        source = pkg.get("source", {})
        local = source.get("editable") or source.get("virtual")
        if local and local != ".":
            paths[pkg["name"]] = Path(local)

    edges = {
        pkg["name"]: {d["name"] for d in pkg.get("dependencies", [])} & set(paths)
        for pkg in lock["package"]
        if pkg["name"] in paths
    }
    return paths, edges


def depends_on(name: str, edges: dict[str, set[str]]) -> set[str]:
    """`name` plus every workspace member it reaches, directly or transitively."""
    seen: set[str] = set()
    stack = [name]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(edges.get(current, ()))
    return seen


def image_name(group: str, path: Path) -> str:
    """`apps/services/cargo-lexical` -> `cargo-lexical`; a nested app keeps its subpath."""
    return "-".join(path.relative_to(Path("apps") / group).parts)


def own_dockerfile_apps(group: str) -> set[Path]:
    """Directories under apps/<group>/ that build from their own Dockerfile."""
    group_root = REPO_ROOT / "apps" / group
    return {
        f.parent.relative_to(REPO_ROOT) for f in group_root.rglob("Dockerfile") if f.parent.is_dir()
    }


def main() -> None:
    changed = changed_files()

    members, edges = workspace_graph()

    affected: list[tuple[str, str, Path]] = []
    for group in GROUPS:
        group_members = {
            name: path for name, path in members.items() if path.parts[:2] == ("apps", group)
        }
        # A member that also carries a Dockerfile is one app, not two.
        standalone = own_dockerfile_apps(group) - set(group_members.values())

        if changed is None or DOCKERFILE in changed:
            # No prior commit to diff against, or the shared Dockerfile
            # changed (every app without its own is built from it): build
            # everything.
            group_affected = set(group_members.values()) | standalone
        elif not changed:
            # Everything in the range was ignorable (docs and the like).
            group_affected = set()
        else:
            changed_members = {
                name for name, path in members.items() if any(path in f.parents for f in changed)
            }
            group_affected = {
                path
                for name, path in group_members.items()
                if depends_on(name, edges) & changed_members
            }
            # Nothing depends on a non-member app, so its own directory is the
            # whole trigger.
            group_affected |= {p for p in standalone if any(p in f.parents for f in changed)}

        affected.extend((group, image_name(group, path), path) for path in sorted(group_affected))

    for group, name, path in affected:
        print(f"{group} {name} {path}")


if __name__ == "__main__":
    sys.exit(main())
