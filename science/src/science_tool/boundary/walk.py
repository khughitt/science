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


def matches_tracked_path(
    rel_to_root: str,
    globs: tuple[str, ...],
    *,
    case_sensitive: bool = True,
) -> bool:
    """Match the path relative to the root, right-anchored, at any depth."""
    candidate = PurePosixPath(rel_to_root if case_sensitive else rel_to_root.casefold())
    patterns = globs if case_sensitive else tuple(glob.casefold() for glob in globs)
    return any(candidate.match(glob) for glob in patterns)


def _is_nested_repo(directory: Path) -> bool:
    """A submodule or linked worktree has `.git` as a file, not a directory."""
    marker = directory / ".git"
    return marker.is_dir() or marker.is_file()


def _raise_walk_error(error: OSError) -> None:
    raise error


def iter_repo_files(project_root: Path, base: Path | None = None) -> list[str]:
    """List sorted repo-relative opaque leaves while excluding repository internals.

    Nested repositories are pruned in either `.git` form, and symlinked
    directories are never descended into. Both remain visible as the one
    trackable leaf Git records. Only the project root is exempt from
    nested-repository pruning; a supplied base that is itself a nested repository
    is deliberately not exempt.
    """
    top = base if base is not None else project_root
    if top.is_symlink():
        if top == project_root:
            return []
        return [top.relative_to(project_root).as_posix()]
    if not top.is_dir():
        return []

    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(top, onerror=_raise_walk_error, followlinks=False):
        current = Path(dirpath)
        if current != project_root and _is_nested_repo(current):
            found.append(current.relative_to(project_root).as_posix())
            dirnames[:] = []
            continue

        descendants: list[str] = []
        for name in sorted(dirnames):
            if name == ".git":
                continue
            child = current / name
            if child.is_symlink():
                found.append(child.relative_to(project_root).as_posix())
                continue
            descendants.append(name)
        dirnames[:] = descendants
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
        if rel.startswith(prefix) and matches_tracked_path(rel[len(prefix) :], root.tracked)
    ]
