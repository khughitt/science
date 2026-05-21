"""Content-derived change dates for code files, via git."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path


def last_content_change_date(rel_path: str, *, repo_root: Path) -> date | None:
    """Date of the last commit that changed `rel_path` (committer date).

    Commit-only semantics: uncommitted working-tree edits are NOT reflected
    until committed (the graph reflects committed state). Returns None when
    the file is untracked, has no commits, or git is unavailable; rather than
    letting such a registered file silently vanish from freshness, Plan B
    validates that every registered code-file has a committed content date.
    """
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "log", "-1", "--format=%cs", "--", rel_path],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    out = completed.stdout.strip()
    if not out:
        return None
    try:
        return date.fromisoformat(out)
    except ValueError:
        return None
