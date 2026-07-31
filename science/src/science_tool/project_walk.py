"""Shared project-file walking with tool-managed trees pruned before descent."""

from __future__ import annotations

import os
from pathlib import Path
from typing import NoReturn

REFERENCE_SCAN_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".ai",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".snakemake",
        ".tox",
        ".venv",
        ".worktrees",
        "__pycache__",
        "node_modules",
        "worktrees",
    }
)


def _raise_walk_error(error: OSError) -> NoReturn:
    raise error


def iter_project_files(
    project_root: Path,
    *,
    suffixes: frozenset[str] | None = None,
) -> list[Path]:
    """Return regular project files without entering tool-managed or linked trees."""
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(
        project_root,
        topdown=True,
        onerror=_raise_walk_error,
        followlinks=False,
    ):
        dirnames[:] = sorted(name for name in dirnames if name not in REFERENCE_SCAN_SKIP_DIRS)
        root = Path(dirpath)
        for name in sorted(filenames):
            if name in REFERENCE_SCAN_SKIP_DIRS:
                continue
            path = root / name
            if suffixes is not None and path.suffix.lower() not in suffixes:
                continue
            if path.is_file():
                files.append(path)
    return sorted(files)
