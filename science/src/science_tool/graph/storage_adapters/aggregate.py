"""AggregateAdapter — multi-entity (entities.yaml) + single-type aggregate (doc/<plural>/<plural>.{json,yaml})."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from science_model.entities import Entity
from science_model.source_ref import SourceRef

from science_tool.graph.source_records import AggregateRowMeta
from science_tool.graph.storage_adapters.base import StorageAdapter


# Mapping: directory plural → singular kind. Used by single-type aggregate files
# (doc/<plural>/<plural>.{json,yaml}). Mirrors science_model.frontmatter._DIR_TO_TYPE.
_DIR_TO_KIND = {
    # Keep `topics` for compatibility with legacy topic aggregates already
    # present in projects. New semantic authoring should prefer typed entities
    # (`concept`, domain kinds, `mechanism`, etc.) over minting more topics.
    "topics": "topic",
    "datasets": "dataset",
    "hypotheses": "hypothesis",
    "questions": "question",
    "concepts": "concept",
    "observations": "observation",
    "findings": "finding",
    "papers": "paper",
    "methods": "method",
    "experiments": "experiment",
    "workflows": "workflow",
    "models": "model",
}

MULTI_TYPE_AGGREGATE_ROOT_KEYS = {
    "entities.yaml": "entities",
    "terms.yaml": "terms",
}


def multi_type_root_key(filename: str) -> str | None:
    """YAML root key for a multi-type aggregate file (`entities.yaml`/`terms.yaml`), or None.

    The single source of truth for which aggregate files carry multiple entity
    types and under which top-level key their rows live. Consumed by the
    retirement executor so it never re-derives this mapping.
    """
    return MULTI_TYPE_AGGREGATE_ROOT_KEYS.get(filename)


class AggregateAdapter(StorageAdapter):
    """Multi-entity (entities.yaml) + single-type aggregate (doc/<plural>/<plural>.{json,yaml})."""

    name = "aggregate"

    def __init__(self, local_profile: str, virtual_files: dict[str, str] | None = None) -> None:
        self._local_profile = local_profile
        self._items_by_path: dict[str, list[Any]] = {}
        # Optional in-memory file contents keyed by project-relative path, mirroring
        # MarkdownAdapter's virtual_files. The layout migration passes its rewritten
        # entities.yaml/terms.yaml here so the post-move model sees aggregate rows at
        # their renumbered canonical_ids — otherwise a shadow row of a renamed owner
        # keeps its stale slug id and collides with the owner (design §B5/§C4).
        self._virtual_files = virtual_files or {}

    def discover(self, project_root: Path) -> list[SourceRef]:
        self._items_by_path.clear()
        refs: list[SourceRef] = []
        refs.extend(self._discover_multi_type(project_root))
        refs.extend(self._discover_single_type(project_root))
        return refs

    def _discover_multi_type(self, project_root: Path) -> list[SourceRef]:
        refs: list[SourceRef] = []
        base = project_root / "knowledge" / "sources" / self._local_profile
        for file_name, root_key in MULTI_TYPE_AGGREGATE_ROOT_KEYS.items():
            path = base / file_name
            try:
                rel = str(path.relative_to(project_root))
            except ValueError:
                rel = str(path)
            text = self._virtual_files.get(rel)
            if text is None:
                if not path.is_file():
                    continue
                text = path.read_text(encoding="utf-8")
            try:
                data = yaml.safe_load(text) or {}
            except yaml.YAMLError:
                continue
            items = data.get(root_key) or []
            if not isinstance(items, list):
                continue
            self._items_by_path[rel] = items
            for idx, raw in enumerate(items):
                if not isinstance(raw, dict):
                    continue
                refs.append(SourceRef(adapter_name=self.name, path=rel, line=idx))
        return refs

    def _discover_single_type(self, project_root: Path) -> list[SourceRef]:
        refs: list[SourceRef] = []
        for plural, _kind in _DIR_TO_KIND.items():
            for ext in ("json", "yaml"):
                f = project_root / "doc" / plural / f"{plural}.{ext}"
                if not f.is_file():
                    continue
                items = self._read_list(f)
                try:
                    rel = str(f.relative_to(project_root))
                except ValueError:
                    rel = str(f)
                self._items_by_path[rel] = items
                for idx, raw in enumerate(items):
                    if not isinstance(raw, dict):
                        continue
                    refs.append(SourceRef(adapter_name=self.name, path=rel, line=idx))
        return refs

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        """Load one entry from its aggregate file."""
        assert ref.line is not None, "AggregateAdapter SourceRef must carry line (entry index)"
        path = Path(ref.path)
        if not path.is_absolute():
            path = Path.cwd() / path
        if path.name in MULTI_TYPE_AGGREGATE_ROOT_KEYS:
            items = self._items_by_path.get(ref.path)
            if items is None:
                text = self._virtual_files.get(ref.path)
                if text is None:
                    text = path.read_text(encoding="utf-8")
                data = yaml.safe_load(text) or {}
                items = data.get(MULTI_TYPE_AGGREGATE_ROOT_KEYS[path.name]) or []
            raw = dict(items[ref.line])
            if path.name == "terms.yaml":
                raw = self._normalize_term_row(raw)
        else:
            # Single-type: kind from directory name.
            plural = path.parent.name
            kind = _DIR_TO_KIND.get(plural, "unknown")
            items = self._items_by_path.get(ref.path)
            if items is None:
                items = self._read_list(path)
            raw = dict(items[ref.line])
            raw.setdefault("kind", kind)
        # Normalize canonical_id from id if needed.
        if "canonical_id" not in raw and "id" in raw:
            raw["canonical_id"] = raw["id"]
        # Preserve file_path so downstream code has it.
        raw.setdefault("file_path", ref.path)
        return raw

    def on_owner_declared(
        self, *, entity: Entity, ref: SourceRef, raw: dict[str, Any], kind: str
    ) -> AggregateRowMeta | None:
        assert ref.line is not None  # AggregateAdapter always sets the entry index
        sp_raw = raw.get("source_path")
        # Capture from the VALIDATED entity, not raw: entity.primary_external_id
        # is a typed ExternalId (already validated) or None. exclude_none drops the
        # optional `version`, leaving the four required keys.
        pei = entity.primary_external_id
        return AggregateRowMeta(
            path=ref.path,
            line=ref.line,
            canonical_id=entity.canonical_id,
            kind=kind,
            # source_path is unschema'd extra metadata; normalize a malformed
            # (non-string) value to None so the report can't crash.
            source_path=sp_raw if isinstance(sp_raw, str) else None,
            primary_external_id=pei.model_dump(exclude_none=True) if pei is not None else None,
        )

    def _normalize_term_row(self, raw: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(raw)
        canonical_id = normalized.get("canonical_id") or normalized.get("id")
        if isinstance(canonical_id, str) and canonical_id and "kind" not in normalized and ":" in canonical_id:
            normalized["kind"] = canonical_id.split(":", 1)[0]
        normalized.pop("content", None)
        normalized.pop("body", None)
        return normalized

    def _read_list(self, path: Path) -> list[Any]:
        try:
            text = path.read_text(encoding="utf-8")
            if path.suffix == ".json":
                data = json.loads(text)
            else:
                data = yaml.safe_load(text)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, yaml.YAMLError, OSError):
            return []
