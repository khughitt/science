"""Project-local claim registry (`specs/claim-registry.yaml`)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from science_tool.verdict.models import ClaimRegistry, ClaimRegistryEntry
from science_tool.verdict.tokens import Token


@dataclass
class IndexedClaimRegistry:
    """Registry + precomputed ID -> canonical lookup."""

    registry: ClaimRegistry
    _index: dict[str, str] = field(default_factory=dict)

    def resolve(self, claim_id: str) -> str | None:
        return self._index.get(claim_id)

    @property
    def version(self) -> int:
        return self.registry.version

    @property
    def project(self) -> str:
        return self.registry.project

    @property
    def entries(self) -> list[ClaimRegistryEntry]:
        return self.registry.entries


def load_registry(path: Path | str) -> IndexedClaimRegistry:
    """Load a project-local claim registry YAML and index it for resolution."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    entries = [_hydrate_entry(raw) for raw in data.get("claims", []) or []]
    registry = ClaimRegistry(
        version=int(data.get("version", 1)),
        project=str(data.get("project", "")),
        entries=entries,
        conventions=data.get("conventions", {}) or {},
    )
    index: dict[str, str] = {}
    for entry in entries:
        index[entry.id] = entry.id
        for syn in entry.synonyms:
            index.setdefault(syn, entry.id)
    return IndexedClaimRegistry(registry=registry, _index=index)


def _hydrate_entry(raw: dict[str, Any]) -> ClaimRegistryEntry:
    return ClaimRegistryEntry(
        id=str(raw["id"]),
        source=str(raw.get("source", "")),
        definition=str(raw.get("definition", "")),
        predicted_direction=Token.from_str(raw.get("predicted_direction", "[+]")),
        synonyms=list(raw.get("synonyms", []) or []),
        members=list(raw.get("members", []) or []),
        cited_in=list(raw.get("cited_in", []) or []),
    )


def has_registry(
    project_root: Path | str,
    *,
    alt_filename: str | None = None,
) -> bool:
    """Return True iff `<project_root>/specs/claim-registry.yaml` exists.

    If `alt_filename` is provided, look for that filename inside the
    project_root directly (used by test fixtures that don't have a
    `specs/` subdir).
    """
    root = Path(project_root)
    if alt_filename is not None:
        return (root / alt_filename).is_file()
    return (root / "specs" / "claim-registry.yaml").is_file()
