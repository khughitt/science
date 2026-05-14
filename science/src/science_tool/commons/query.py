"""Query the commons registry."""

from __future__ import annotations

import fnmatch
import json
import os
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path

from science_tool.commons.adapter import (
    CommonsEntityAdapter,
    CommonsEntityRecord,
)
from science_tool.commons.errors import CommonsEntityError, CommonsRegistryError
from science_tool.commons.registry import (
    REGISTRY_FILENAME,
    RegistryBuilder,
)


# Column order is load-bearing: `_hydrate` unpacks rows positionally, so both
# SELECTs (`find` and `_row_for`) must use this exact list.
_ENTITY_COLUMNS = (
    "canonical_id, type, slug, title, schema_profile, body_path, "
    "datapackage_path, mtime_ns, frontmatter_json"
)


class CommonsQuery:
    """Read-only access to the commons registry. Warns (does not rebuild) on staleness."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._adapter = CommonsEntityAdapter(root)
        self._builder = RegistryBuilder(root, self._adapter)

    def show(self, canonical_id: str) -> CommonsEntityRecord:
        self._require_registry()
        self._warn_if_stale()
        row = self._row_for(canonical_id)
        if row is None:
            raise CommonsEntityError(
                self._root,
                canonical_id=canonical_id,
                cause=KeyError(canonical_id),
            )
        return self._hydrate(row)

    def find(
        self,
        type: str,
        *,
        tags: Sequence[str] = (),
        ontology_terms: Sequence[str] = (),
        year_from: int | None = None,
        year_to: int | None = None,
        slug_glob: str | None = None,
    ) -> list[CommonsEntityRecord]:
        if (year_from is not None or year_to is not None) and type != "paper":
            raise ValueError(
                f"year filters are only valid for type='paper', got type={type!r}"
            )
        self._require_registry()
        self._warn_if_stale()
        clauses = ["type = ?"]
        params: list[str] = [type]
        for tag in tags:
            clauses.append(
                "canonical_id IN (SELECT canonical_id FROM entity_tags WHERE tag = ?)"
            )
            params.append(tag)
        for term in ontology_terms:
            clauses.append(
                "canonical_id IN (SELECT canonical_id FROM entity_ontology_terms WHERE term = ?)"
            )
            params.append(term)
        sql = (
            f"SELECT {_ENTITY_COLUMNS} FROM entities "
            f"WHERE {' AND '.join(clauses)} ORDER BY canonical_id"
        )
        try:
            conn = sqlite3.connect(self._root / REGISTRY_FILENAME)
            try:
                rows = conn.execute(sql, params).fetchall()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise CommonsRegistryError(
                self._root / REGISTRY_FILENAME, cause=exc
            ) from exc
        records = [self._hydrate(row) for row in rows]
        if slug_glob is not None:
            records = [r for r in records if fnmatch.fnmatch(r.slug, slug_glob)]
        if year_from is not None or year_to is not None:
            records = [
                r
                for r in records
                if _year_in_range(r.frontmatter.get("year"), year_from, year_to)
            ]
        return records

    def _require_registry(self) -> None:
        """Raise CommonsRegistryError if the registry is absent or malformed.

        sqlite3.connect() creates an empty database when the file is missing,
        so a naive query against a non-existent registry would surface as a
        bare `OperationalError: no such table: entities` rather than a
        CommonsError. Probe explicitly.
        """
        db_path = self._root / REGISTRY_FILENAME
        if not db_path.is_file():
            raise CommonsRegistryError(
                db_path,
                cause=FileNotFoundError(
                    f"registry not found at {db_path}; "
                    "run `science commons index rebuild`"
                ),
            )
        try:
            conn = sqlite3.connect(db_path)
            try:
                row = conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name = 'entities'"
                ).fetchone()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise CommonsRegistryError(db_path, cause=exc) from exc
        if row is None:
            raise CommonsRegistryError(
                db_path,
                cause=RuntimeError(
                    "registry exists but is missing the entities table; "
                    "run `science commons index rebuild`"
                ),
            )

    def _row_for(self, canonical_id: str) -> tuple | None:
        try:
            conn = sqlite3.connect(self._root / REGISTRY_FILENAME)
            try:
                return conn.execute(
                    f"SELECT {_ENTITY_COLUMNS} FROM entities WHERE canonical_id = ?",
                    (canonical_id,),
                ).fetchone()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise CommonsRegistryError(
                self._root / REGISTRY_FILENAME, cause=exc
            ) from exc

    def _hydrate(self, row: tuple) -> CommonsEntityRecord:
        (
            canonical_id,
            type_,
            slug,
            _title,
            schema_profile,
            body_path,
            dp_path,
            mtime_ns,
            frontmatter_json,
        ) = row
        return CommonsEntityRecord(
            canonical_id=canonical_id,
            type=type_,
            slug=slug,
            schema_profile=schema_profile,
            frontmatter=json.loads(frontmatter_json),
            body_path=self._root / body_path,
            datapackage_path=(self._root / dp_path) if dp_path else None,
            mtime_ns=int(mtime_ns),
        )

    def _warn_if_stale(self) -> None:
        if os.environ.get("SCIENCE_COMMONS_QUIET_STALE"):
            return
        if self._builder.is_stale():
            print(
                "warning: commons registry is stale; run `science commons index rebuild`",
                file=sys.stderr,
            )


def _year_in_range(year: object, lo: int | None, hi: int | None) -> bool:
    if not isinstance(year, int):
        return False
    if lo is not None and year < lo:
        return False
    if hi is not None and year > hi:
        return False
    return True
