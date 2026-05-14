"""Walk a commons store and produce validated entity records.

In Phase B the adapter parses frontmatter, validates against
Phase A's EntityValidator, and emits CommonsEntityRecord (or
CommonsEntityError) per entity. The validated frontmatter dict is
carried as-is - no `science_model.Entity` materialization (deferred
to Phase D, see the design spec).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.errors import CommonsEntityError, CommonsLayoutError

_TYPE_DIRS = ("datasets", "papers", "topics", "themes")
_SKIP_NAMES = frozenset({".git", ".migrations", "__pycache__", "registry.sqlite"})


@dataclass(frozen=True, slots=True)
class CommonsEntityRecord:
    """One validated entity from the commons store."""

    canonical_id: str           # "<type>:<slug>", e.g. "dataset:cath-domains"
    type: str                   # "dataset" | "paper" | "topic" | "theme"
    slug: str
    schema_profile: str
    frontmatter: dict[str, Any]  # validated against schema_profile
    body_path: Path             # absolute path to entity.md
    datapackage_path: Path | None  # sibling datapackage.yaml (datasets only)
    mtime_ns: int               # max st_mtime_ns over (body_path, datapackage_path)


class CommonsEntityAdapter:
    """Walk the commons store and yield records or per-entity errors."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def scan(self) -> Iterator[CommonsEntityRecord | CommonsEntityError]:
        for type_name in _TYPE_DIRS:
            type_dir = self._root / type_name
            if not type_dir.is_dir():
                continue
            yield from self._scan_type(type_name, type_dir)

    def _scan_type(
        self, type_name: str, type_dir: Path
    ) -> Iterator[CommonsEntityRecord | CommonsEntityError]:
        if type_name == "datasets":
            for child in sorted(type_dir.iterdir()):
                if child.name in _SKIP_NAMES or child.name.startswith("."):
                    continue
                if not child.is_dir():
                    continue
                entity_path = child / "entity.md"
                dp_path = child / "datapackage.yaml"
                if not entity_path.is_file():
                    # Empty dataset directory (e.g., .gitkeep'd); skip silently.
                    continue
                if not dp_path.is_file():
                    raise CommonsLayoutError(
                        child,
                        reason=f"dataset directory missing required datapackage.yaml sibling",
                    )
                yield self._make_record(type_name, child.name, entity_path, dp_path)
        else:
            for child in sorted(type_dir.iterdir()):
                if child.name in _SKIP_NAMES or child.name.startswith("."):
                    continue
                if child.is_dir():
                    continue
                if child.suffix != ".md":
                    continue
                slug = child.stem
                yield self._make_record(type_name, slug, child, None)

    def _make_record(
        self,
        type_dir: str,
        slug: str,
        body_path: Path,
        datapackage_path: Path | None,
    ) -> CommonsEntityRecord | CommonsEntityError:
        # Parsing/validation arrives in Task 6. For now, build a stub record so
        # the walking tests pass.
        canonical_id = f"{_TYPE_DIR_TO_TYPE[type_dir]}:{slug}"
        mtime_ns = body_path.stat().st_mtime_ns
        if datapackage_path is not None:
            mtime_ns = max(mtime_ns, datapackage_path.stat().st_mtime_ns)
        return CommonsEntityRecord(
            canonical_id=canonical_id,
            type=_TYPE_DIR_TO_TYPE[type_dir],
            slug=slug,
            schema_profile="",  # filled in Task 6
            frontmatter={},     # filled in Task 6
            body_path=body_path,
            datapackage_path=datapackage_path,
            mtime_ns=mtime_ns,
        )


_TYPE_DIR_TO_TYPE = {
    "datasets": "dataset",
    "papers": "paper",
    "topics": "topic",
    "themes": "theme",
}
