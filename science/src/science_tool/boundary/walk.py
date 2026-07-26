"""Filesystem walk under a manifest root.

`unreachable-tracked` must find files git CANNOT see, so it cannot ask git for
them. Semantics fixed here:

* symlinked DIRECTORIES are never descended into -- prevents cycles and stops
  the walk escaping the root; a symlinked tree is not in the repository
* symlinked FILES are reported, because git tracks the link itself
* a directory containing `.git` is pruned: git treats a nested repository as an
  opaque gitlink and never looks inside
* `.git` itself is always skipped
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from science_tool.boundary.config import BoundaryRoot


def _matches(rel_to_root: str, globs: tuple[str, ...]) -> bool:
    """Match the path relative to the root, right-anchored, at any depth."""
    candidate = PurePosixPath(rel_to_root)
    return any(candidate.match(glob) for glob in globs)


def _is_nested_repo(directory: Path) -> bool:
    """A submodule or linked worktree has `.git` as a file, not a directory."""
    marker = directory / ".git"
    return marker.is_dir() or marker.is_file()


def _raise_walk_error(error: OSError) -> None:
    raise error


def iter_repo_files(project_root: Path, base: Path | None = None) -> list[str]:
    """List sorted repo-relative paths while excluding repository internals.

    Nested repositories are pruned in either `.git` form, and symlinked
    directories are never descended into. Only the project root is exempt from
    nested-repository pruning; a supplied base that is itself a nested
    repository is deliberately not exempt.
    """
    top = base if base is not None else project_root
    if top.is_symlink() or not top.is_dir():
        return []

    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(top, onerror=_raise_walk_error, followlinks=False):
        current = Path(dirpath)
        if current != project_root and _is_nested_repo(current):
            dirnames[:] = []
            continue

        dirnames[:] = sorted(d for d in dirnames if d != ".git" and not (current / d).is_symlink())
        for name in sorted(n for n in filenames if n != ".git"):
            found.append((current / name).relative_to(project_root).as_posix())

    return sorted(found)


def manifest_candidates(project_root: Path, root: BoundaryRoot) -> list[str]:
    """Return repo-relative tracked-glob matches under a manifest root."""
    base = project_root / root.path
    prefix = f"{root.path}/"
    return [
        rel
        for rel in iter_repo_files(project_root, base)
        if _matches(rel[len(prefix) :], root.tracked)
    ]
