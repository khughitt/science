"""AggregateAdapter — multi-entity (entities.yaml) + single-type aggregate (doc/<plural>/<plural>.{json,yaml})."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from science_model.source_ref import SourceRef

from science_tool.graph.storage_adapters.base import StorageAdapter


# Mapping: directory plural → singular kind. Used by single-type aggregate files
# (doc/<plural>/<plural>.{json,yaml}). Mirrors science_model.frontmatter._DIR_TO_TYPE.
_DIR_TO_KIND = {
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


class AggregateAdapter(StorageAdapter):
    """Multi-entity (entities.yaml) + single-type aggregate (doc/<plural>/<plural>.{json,yaml})."""

    name = "aggregate"

    def __init__(self, local_profile: str) -> None:
        self._local_profile = local_profile

    def discover(self, project_root: Path) -> list[SourceRef]:
        refs: list[SourceRef] = []
        refs.extend(self._discover_multi_type(project_root))
        refs.extend(self._discover_single_type(project_root))
        return refs

    def _discover_multi_type(self, project_root: Path) -> list[SourceRef]:
        path = project_root / "knowledge" / "sources" / self._local_profile / "entities.yaml"
        if not path.is_file():
            return []
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return []
        items = data.get("entities") or []
        if not isinstance(items, list):
            return []
        try:
            rel = str(path.relative_to(project_root))
        except ValueError:
            rel = str(path)
        refs: list[SourceRef] = []
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
        if path.name == "entities.yaml":
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            items = data.get("entities") or []
            raw = dict(items[ref.line])
            # Kind from entry itself.
        else:
            # Single-type: kind from directory name.
            plural = path.parent.name
            kind = _DIR_TO_KIND.get(plural, "unknown")
            items = self._read_list(path)
            raw = dict(items[ref.line])
            raw.setdefault("kind", kind)
        # Normalize canonical_id from id if needed.
        if "canonical_id" not in raw and "id" in raw:
            raw["canonical_id"] = raw["id"]
        # Preserve file_path so downstream code has it.
        raw.setdefault("file_path", ref.path)
        return raw

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
