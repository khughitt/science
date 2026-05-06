"""DatapackageAdapter — datasets promoted to live as <dir>/datapackage.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from science_model.source_ref import SourceRef

from science_tool.graph.storage_adapters.base import StorageAdapter


_ENTITY_FIELDS = (
    "id",
    "canonical_id",
    "type",
    "kind",
    "title",
    "description",
    "status",
    "origin",
    "access",
    "derivation",
    "accessions",
    "datapackage",
    "local_path",
    "consumed_by",
    "parent_dataset",
    "siblings",
    "ontology_terms",
    "related",
    "source_refs",
    "same_as",
    "aliases",
)


class EntityDatapackageInvalidError(ValueError):
    """Raised when a science-pkg-entity-1.0 datapackage is missing required entity fields."""

    def __init__(self, datapackage_path: str, message: str) -> None:
        super().__init__(f"{datapackage_path}: invalid entity-profile datapackage — {message}")


class DatapackageAdapter(StorageAdapter):
    name = "datapackage"

    def __init__(self, scan_roots: list[str] | None = None) -> None:
        self._scan_roots = scan_roots or ["data", "results"]

    def discover(self, project_root: Path) -> list[SourceRef]:
        refs: list[SourceRef] = []
        for rel in self._scan_roots:
            root = project_root / rel
            if not root.is_dir():
                continue
            for dp_path in sorted(root.rglob("datapackage.yaml")):
                try:
                    dp = yaml.safe_load(dp_path.read_text(encoding="utf-8")) or {}
                except (yaml.YAMLError, OSError):
                    continue  # malformed → can't tell if entity; skip quietly
                profiles = dp.get("profiles") or []
                if "science-pkg-entity-1.0" not in profiles:
                    continue  # non-entity datapackage → ignore
                try:
                    rel_path = str(dp_path.relative_to(project_root))
                except ValueError:
                    rel_path = str(dp_path)
                # Fail-fast validation: entity-profile must carry required fields.
                for field in ("id", "type", "title"):
                    if not dp.get(field):
                        raise EntityDatapackageInvalidError(
                            rel_path,
                            f"missing required entity field {field!r} (science-pkg-entity-1.0 profile present)",
                        )
                refs.append(SourceRef(adapter_name=self.name, path=rel_path))
        return refs

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        path = Path(ref.path)
        if not path.is_absolute():
            path = Path.cwd() / path
        dp = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        raw = {k: dp[k] for k in _ENTITY_FIELDS if k in dp}
        raw.setdefault("kind", raw.get("type") or "dataset")
        raw.setdefault("canonical_id", raw.get("id", ""))
        raw.setdefault("file_path", ref.path)
        return raw
