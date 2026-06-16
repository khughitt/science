# science/src/science_tool/entity_scan.py
"""The sole sanctioned recursive scanner of canonical entity markdown (P3).

Archived entities live under ``entities/_archive/``. This iterator is the ONE
place that decides what counts as a live entity file: it skips any ``_``-prefixed
path segment below the entities root, and — only when ``include_archived`` is set —
un-skips the single reserved ``_archive`` subtree. Every recursive ``entities/``
scan must route through here so the archive skip cannot regress (enforced by the
guard test). Stdlib-only leaf module (no science_tool imports) to avoid cycles.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

ARCHIVE_SEGMENT = "_archive"


def iter_entity_markdown(entities_root: Path, *, include_archived: bool = False) -> Iterator[Path]:
    """Yield ``*.md`` files under ``entities_root`` in sorted order, skipping any
    ``_``-prefixed segment. When ``include_archived`` is True, the single
    ``_archive`` segment is NOT a skip reason (other ``_``-prefixed segments still
    are). Missing root yields nothing.
    """
    if not entities_root.is_dir():
        return
    for path in sorted(entities_root.rglob("*.md")):
        rel_parts = path.relative_to(entities_root).parts[:-1]  # exclude filename
        hidden = [seg for seg in rel_parts if seg.startswith("_")]
        if not hidden:
            yield path
            continue
        if include_archived and hidden == [ARCHIVE_SEGMENT]:
            yield path
