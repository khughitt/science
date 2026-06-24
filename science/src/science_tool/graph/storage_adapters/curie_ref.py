# src/science_tool/graph/storage_adapters/curie_ref.py
"""CurieRefAdapter — the project ontology cross-reference authority
(`knowledge/sources/<profile>/external_refs.yaml`) as an external-reference
source (design §B2/§B3a/§C3, Phase 4c).

Synthesizes a lightweight `<kind>:<slug>` raw record per row, carrying the curie
in `same_as` so materialization emits a skos:exactMatch to a URIRef external-term
node. These are external references, not owners: the load loop tags their identity
rows ParticipationMode.EXTERNAL_REFERENCE (never renumbered, never a collision).

Unlike a transitional aggregate row (debt the triage tolerates), this file is the
DURABLE backing authority once aggregate rows retire, so both integrity failures
-- a duplicate id, or a malformed primary_external_id -- raise loudly rather than
silently drop a row (which would unresolve citations or lose a curie mapping).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from science_model.source_ref import SourceRef

from science_tool.graph.identity_table import ParticipationMode
from science_tool.graph.storage_adapters.base import StorageAdapter

_FILE_NAME = "external_refs.yaml"
_ROOT_KEY = "references"

# NOTE: do NOT import `local_profile_sources_dir` from `science_tool.graph.sources`
# here — Task 6 registers this adapter *inside* sources.py, so importing from
# sources would create a circular import at module load. Build the path directly
# from the resolved `local_profile`, exactly as AggregateAdapter does
# (`project_root / "knowledge" / "sources" / self._local_profile`). The profile is
# still resolved (passed in by the loader), so nothing is hardcoded except the
# universal `knowledge/sources` structural prefix that AggregateAdapter also fixes.


class CurieRefAdapter(StorageAdapter):
    """Reads `external_refs.yaml` into external-reference curie records."""

    name = "curie-ref"
    participation_mode = ParticipationMode.EXTERNAL_REFERENCE

    def __init__(self, *, local_profile: str) -> None:
        self._local_profile = local_profile
        self._rows: list[dict[str, Any]] = []
        self._rel: str | None = None

    def _path(self, project_root: Path) -> Path:
        # Mirror AggregateAdapter's path construction (no sources.py import; see module note).
        return project_root / "knowledge" / "sources" / self._local_profile / _FILE_NAME

    def discover(self, project_root: Path) -> list[SourceRef]:
        self._rows = []
        path = self._path(project_root)
        self._rel = path.relative_to(project_root).as_posix()
        if not path.is_file():
            return []
        raw_doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        data = {} if raw_doc is None else raw_doc
        if not isinstance(data, dict):
            raise ValueError(f"{self._rel}: document root must be a mapping (got {type(data).__name__})")
        # Use .get(key, []) — NOT `.get(key) or []`: a present-but-non-list value
        # (references: {}, references: "", or a bare `references:` -> None) must reach
        # the isinstance check and fail loud, not be silently coerced to "no refs".
        # Only a genuinely absent key defaults to the empty authority.
        rows = data.get(_ROOT_KEY, [])
        if not isinstance(rows, list):
            raise ValueError(f"{self._rel}: `{_ROOT_KEY}` must be a list (got {type(rows).__name__})")
        seen: set[str] = set()
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ValueError(f"{self._rel}[{i}]: each reference must be a mapping")
            cid = row.get("id")
            if not isinstance(cid, str) or not cid:
                raise ValueError(f"{self._rel}[{i}]: reference requires a non-empty `id`")
            if cid in seen:
                raise ValueError(f"{self._rel}: duplicate id {cid!r} in external-reference authority")
            seen.add(cid)
            pei = row.get("primary_external_id")
            # Require the full ExternalId shape (source, id, curie, provenance): these
            # rows are validated as ExternalId downstream (sources.py:359) once T6
            # registers the adapter, and external_refs.yaml is the durable backing
            # authority — so a partial mapping must fail loud here, not be skipped later.
            if not (
                isinstance(pei, dict)
                and all(isinstance(pei.get(k), str) and pei.get(k) for k in ("source", "id", "curie", "provenance"))
            ):
                raise ValueError(
                    f"{self._rel}[{i}] ({cid}): malformed primary_external_id "
                    "(needs string `source`, `id`, `curie`, `provenance`)"
                )
        self._rows = rows
        return [SourceRef(adapter_name=self.name, path=self._rel, line=i) for i in range(len(rows))]

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        if not self._rows:
            raise RuntimeError("CurieRefAdapter.discover() must be called before load_raw()")
        assert ref.line is not None, "CurieRefAdapter SourceRef must carry line (row index)"
        assert self._rel is not None
        row = self._rows[ref.line]
        cid = row["id"]
        kind = row.get("type") or cid.split(":", 1)[0]
        curie = row["primary_external_id"]["curie"]
        raw: dict[str, Any] = {
            "kind": kind,
            "id": cid,
            "title": row.get("title") or cid,
            "same_as": [curie],  # LIST: _enrich_raw normalizes same_as only when isinstance(vals, list)
            "file_path": self._rel,
            "primary_external_id": row["primary_external_id"],
        }
        description = row.get("description")
        if isinstance(description, str) and description:
            raw["summary"] = description
        taxon = row.get("taxon")
        if isinstance(taxon, str) and taxon:
            raw["taxon"] = taxon
        return raw
