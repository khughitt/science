# science/src/science_tool/archive.py
"""Archive tier (P3): append-only index, relocation, and index-only resolution.

The active archive index — never archived-markdown scanning — is the source of
truth for archived-id resolution. Rows are append-only; reversal appends an
``unarchive`` tombstone. ``load_archive_index`` folds rows last-write-wins per id.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1
ARCHIVE_SEGMENT = "_archive"
DEFAULT_ARCHIVE_STATUSES = frozenset({"superseded", "archived"})


class ArchiveRow(BaseModel):
    """One append-only operation. ``op`` discriminates archive vs unarchive; the
    P4-reserved fields (digest_insight/consolidated_into/cluster_id) are simply
    absent in P3 and read via ``.get``-style optional access."""
    schema_version: int = SCHEMA_VERSION
    op: str  # "archive" | "unarchive"
    id: str
    kind: str | None = None
    title: str | None = None
    aliases: list[str] = Field(default_factory=list)
    same_as: list[str] = Field(default_factory=list)
    status: str | None = None
    superseded_by: str | None = None
    original_path: str | None = None
    archived_at: str | None = None
    reason: str | None = None
    restored_path: str | None = None
    unarchived_at: str | None = None


class ArchiveIndex(BaseModel):
    active_by_id: dict[str, ArchiveRow] = Field(default_factory=dict)

    def resolvable_ids(self) -> dict[str, str]:
        """alias/same_as/canonical -> canonical_id over ACTIVE entries only."""
        out: dict[str, str] = {}
        for canonical, row in self.active_by_id.items():
            out[canonical] = canonical
            for other in (*row.aliases, *row.same_as):
                out[other] = canonical
        return out


def archive_index_path(project_root: Path) -> Path:
    return project_root / "entities" / ARCHIVE_SEGMENT / "archive-index.jsonl"


def derive_archive_path(original_rel: str) -> str:
    """`entities/<rest>` -> `entities/_archive/<rest>` (kind subtree mirrored)."""
    parts = Path(original_rel).parts
    if not parts or parts[0] != "entities":
        raise ValueError(f"archive path must be under entities/: {original_rel!r}")
    return Path("entities", ARCHIVE_SEGMENT, *parts[1:]).as_posix()


def _fsync_dir(directory: Path) -> None:
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def append_row(index_path: Path, row: ArchiveRow) -> None:
    """Append one complete JSON line and fsync the index file + parent dir."""
    index_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row.model_dump(), sort_keys=True) + "\n"
    with open(index_path, "a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())
    _fsync_dir(index_path.parent)


def load_archive_index(project_root: Path) -> ArchiveIndex:
    """Fold rows last-write-wins per id; an id whose latest op is ``unarchive`` is
    dropped from the active set."""
    path = archive_index_path(project_root)
    active: dict[str, ArchiveRow] = {}
    if not path.is_file():
        return ArchiveIndex(active_by_id=active)
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        row = ArchiveRow.model_validate_json(raw)
        if row.op == "archive":
            active[row.id] = row
        elif row.op == "unarchive":
            active.pop(row.id, None)
    return ArchiveIndex(active_by_id=active)
