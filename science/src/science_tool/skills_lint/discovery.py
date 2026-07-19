from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

TEMPLATES_PREFIX = "meta/templates/"


def iter_skill_files(root: Path) -> Iterator[Path]:
    """Yield every skill-tree Markdown file, sorted, EXCLUDING authoring scaffolds
    under ``meta/templates/``. ``INDEX.md`` is intentionally included — the linter
    must inspect it (e.g. to reject ``archetype:`` on the index). Consumers apply
    their own structural-role filters after iterating."""
    for path in sorted(root.rglob("*.md")):
        if path.relative_to(root).as_posix().startswith(TEMPLATES_PREFIX):
            continue
        yield path
