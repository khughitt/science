"""Worktree state primitives: clean check, dirty paths, conflict detection."""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path


def in_git_repo(path: Path) -> bool:
    """True if *path* is inside a git working tree."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except FileNotFoundError:
        return False


def is_clean(repo_root: Path) -> bool:
    """True if the worktree has no modifications, additions, deletions, or untracked files."""
    if not in_git_repo(repo_root):
        return False
    result = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip() == ""


def dirty_paths(repo_root: Path) -> set[Path]:
    """Return paths that are modified, added, deleted, or untracked."""
    if not in_git_repo(repo_root):
        return set()
    result = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    out: set[Path] = set()
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        # porcelain v1 lines: "XY <path>" or "XY <orig> -> <new>"
        path_part = line[3:].split(" -> ")[-1]
        out.add(Path(path_part))
    return out


def paths_intersect(touched_globs: list[str], dirty: set[Path]) -> set[Path]:
    """Return the subset of *dirty* paths matched by any glob in *touched_globs*."""
    matched: set[Path] = set()
    for p in dirty:
        for glob in touched_globs:
            if fnmatch.fnmatch(str(p), glob):
                matched.add(p)
                break
    return matched
