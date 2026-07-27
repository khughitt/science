from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

EXCLUDED_PREFIXES = ("generated/", "meta/templates/")


def iter_skill_files(root: Path) -> Iterator[Path]:
    """Yield every authored skill-tree Markdown file, sorted.

    Generated distribution files and authoring scaffolds are excluded. ``INDEX.md``
    is intentionally included — the linter must inspect it (e.g. to reject
    ``archetype:`` on the index). Consumers apply their own structural-role filters
    after iterating.
    """
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(EXCLUDED_PREFIXES):
            continue
        yield path
