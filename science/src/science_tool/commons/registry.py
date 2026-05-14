"""SQLite index over a commons store.

The registry is regenerable: filesystem is the source of truth. Phase B
always does a full rebuild (drop + recreate); incremental rebuilds are
deferred to Phase E.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from science_tool.commons.adapter import (
    CommonsEntityAdapter,
    CommonsEntityRecord,
)
from science_tool.commons.errors import CommonsEntityError, CommonsRegistryError

REGISTRY_FILENAME = "registry.sqlite"
REGISTRY_SCHEMA_VERSION = "1"

_DDL = """
CREATE TABLE schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE entities (
    canonical_id     TEXT PRIMARY KEY,
    type             TEXT NOT NULL,
    slug             TEXT NOT NULL,
    title            TEXT,
    schema_profile   TEXT NOT NULL,
    body_path        TEXT NOT NULL,
    datapackage_path TEXT,
    mtime_ns         INTEGER NOT NULL,
    frontmatter_json TEXT NOT NULL
);
CREATE INDEX idx_entities_type_slug ON entities (type, slug);

CREATE TABLE entity_tags (
    canonical_id TEXT NOT NULL REFERENCES entities(canonical_id) ON DELETE CASCADE,
    tag          TEXT NOT NULL,
    PRIMARY KEY (canonical_id, tag)
);
CREATE INDEX idx_entity_tags_tag ON entity_tags (tag);

CREATE TABLE entity_ontology_terms (
    canonical_id TEXT NOT NULL REFERENCES entities(canonical_id) ON DELETE CASCADE,
    term         TEXT NOT NULL,
    PRIMARY KEY (canonical_id, term)
);
CREATE INDEX idx_entity_ontology_terms_term ON entity_ontology_terms (term);
"""


@dataclass(frozen=True)
class RebuildReport:
    entities_indexed: int
    errors: list[CommonsEntityError]
    duration_ms: int


class RegistryBuilder:
    """Build (and rebuild) the commons SQLite registry."""

    def __init__(self, root: Path, adapter: CommonsEntityAdapter) -> None:
        self._root = root
        self._adapter = adapter

    @property
    def db_path(self) -> Path:
        return self._root / REGISTRY_FILENAME

    def rebuild(self) -> RebuildReport:
        start = time.perf_counter()
        records: list[CommonsEntityRecord] = []
        errors: list[CommonsEntityError] = []
        for item in self._adapter.scan():
            if isinstance(item, CommonsEntityError):
                errors.append(item)
            else:
                records.append(item)

        # Write to a unique temp file, then atomically rename.
        with tempfile.NamedTemporaryFile(
            dir=self._root, prefix=".registry-", suffix=".sqlite", delete=False
        ) as handle:
            temp_path = Path(handle.name)
        try:
            conn = sqlite3.connect(temp_path)
            try:
                conn.executescript(_DDL)
                self._insert_records(conn, records)
                self._write_schema_meta(conn, records)
                conn.commit()
            finally:
                conn.close()
            temp_path.replace(self.db_path)
        except Exception as exc:
            if temp_path.exists():
                temp_path.unlink()
            raise CommonsRegistryError(self.db_path, cause=exc) from exc

        duration_ms = int((time.perf_counter() - start) * 1000)
        return RebuildReport(
            entities_indexed=len(records),
            errors=errors,
            duration_ms=duration_ms,
        )

    def _insert_records(
        self,
        conn: sqlite3.Connection,
        records: Iterable[CommonsEntityRecord],
    ) -> None:
        for record in records:
            body_rel = record.body_path.relative_to(self._root).as_posix()
            dp_rel = (
                record.datapackage_path.relative_to(self._root).as_posix()
                if record.datapackage_path is not None
                else None
            )
            conn.execute(
                "INSERT INTO entities (canonical_id, type, slug, title, schema_profile, "
                "body_path, datapackage_path, mtime_ns, frontmatter_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.canonical_id,
                    record.type,
                    record.slug,
                    record.frontmatter.get("title"),
                    record.schema_profile,
                    body_rel,
                    dp_rel,
                    record.mtime_ns,
                    json.dumps(record.frontmatter, sort_keys=True),
                ),
            )
            tags = record.frontmatter.get("tags") or []
            for tag in tags:
                conn.execute(
                    "INSERT OR IGNORE INTO entity_tags (canonical_id, tag) VALUES (?, ?)",
                    (record.canonical_id, str(tag)),
                )
            terms = record.frontmatter.get("ontology_terms") or []
            for term in terms:
                conn.execute(
                    "INSERT OR IGNORE INTO entity_ontology_terms (canonical_id, term) "
                    "VALUES (?, ?)",
                    (record.canonical_id, str(term)),
                )

    def _write_schema_meta(
        self,
        conn: sqlite3.Connection,
        records: list[CommonsEntityRecord],
    ) -> None:
        source_files = sorted(self._source_files())
        rel_posix = [p.relative_to(self._root).as_posix() for p in source_files]
        digest = hashlib.sha256("\n".join(rel_posix).encode("utf-8")).hexdigest()
        max_mtime = max((p.stat().st_mtime_ns for p in source_files), default=0)
        rows = {
            "schema_version": REGISTRY_SCHEMA_VERSION,
            "store_root": str(self._root.resolve()),
            "source_count": str(len(source_files)),
            "max_source_mtime_ns": str(max_mtime),
            "source_paths_digest": digest,
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        for key, value in rows.items():
            conn.execute(
                "INSERT INTO schema_meta (key, value) VALUES (?, ?)",
                (key, value),
            )

    def _source_files(self) -> list[Path]:
        """Same walk the adapter uses, but flattened to file paths."""
        from science_tool.commons.adapter import (
            _SKIP_NAMES,
            _TYPE_DIRS,
        )

        files: list[Path] = []
        for type_dir in _TYPE_DIRS:
            base = self._root / type_dir
            if not base.is_dir():
                continue
            if type_dir == "datasets":
                for child in base.iterdir():
                    if child.name in _SKIP_NAMES or child.name.startswith("."):
                        continue
                    if not child.is_dir():
                        continue
                    body = child / "entity.md"
                    dp = child / "datapackage.yaml"
                    if body.is_file():
                        files.append(body)
                    if dp.is_file():
                        files.append(dp)
            else:
                for child in base.iterdir():
                    if child.name in _SKIP_NAMES or child.name.startswith("."):
                        continue
                    if child.is_dir():
                        continue
                    if child.suffix != ".md":
                        continue
                    files.append(child)
        return files
