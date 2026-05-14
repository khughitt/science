"""Bootstrap a new commons store on disk."""

from __future__ import annotations

import subprocess
from pathlib import Path

from science_tool.commons.errors import CommonsRootMalformedError

_TYPE_DIRS = ("datasets", "papers", "topics", "themes")

_README_TEXT = """# Science Commons

This directory is a shared knowledge store for the Science framework. It holds
curated, citable entities — datasets, papers, topics, themes — consumed across
projects via the `science commons` CLI.

Files are the source of truth. `registry.sqlite` is a regenerable index built
by `science commons index rebuild`; `.migrations/` is an audit log written by
`science promote` (Phase E and later). Both are gitignored.

See `~/d/science/docs/plans/2026-05-13-multiproject-schema-and-shared-store-design.md`
for the design.
"""

_GITIGNORE_TEXT = """# Regenerable index (rebuild from filesystem with `science commons index rebuild`)
registry.sqlite
registry.sqlite-journal
.registry-*.sqlite

# Promotion audit log (written by `science promote`, Phase E+)
.migrations/

# Python build artifacts
__pycache__/
"""


def _has_layout(root: Path) -> list[str]:
    """Return the list of expected layout entries that are missing under root."""
    missing: list[str] = []
    if not (root / ".git").is_dir():
        missing.append(".git")
    for sub in _TYPE_DIRS:
        if not (root / sub).is_dir():
            missing.append(sub)
    return missing


def init_commons(root: Path, *, force: bool = False) -> None:
    """Create or verify the commons store layout at `root`.

    - If `root` does not exist, create it and the full layout.
    - If `root` exists and has the layout, no-op (idempotent).
    - If `root` exists but lacks the layout, raise CommonsRootMalformedError
      unless `force=True`.
    """
    if root.exists():
        missing = _has_layout(root)
        if not missing:
            return  # already initialized
        if not force and any(root.iterdir()):
            raise CommonsRootMalformedError(root, missing=missing)
    else:
        root.mkdir(parents=True)

    if not (root / ".git").is_dir():
        subprocess.run(
            ["git", "init", "--quiet", str(root)],
            check=True,
        )

    readme = root / "README.md"
    if not readme.is_file():
        readme.write_text(_README_TEXT, encoding="utf-8")

    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        gitignore.write_text(_GITIGNORE_TEXT, encoding="utf-8")

    for sub in _TYPE_DIRS:
        sub_dir = root / sub
        sub_dir.mkdir(exist_ok=True)
        gitkeep = sub_dir / ".gitkeep"
        if not gitkeep.is_file():
            gitkeep.write_text("", encoding="utf-8")
