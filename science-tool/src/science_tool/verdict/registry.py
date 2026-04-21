"""Project-local claim registry (`specs/claim-registry.yaml`)."""

from __future__ import annotations

from collections.abc import Mapping
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
    if not isinstance(data, Mapping):
        raise ValueError("Malformed claim registry: top-level mapping is required")

    raw_claims = data.get("claims", [])
    if not isinstance(raw_claims, list):
        raise ValueError("Malformed claim registry: claims must be a list")

    entries = [_hydrate_entry(raw) for raw in raw_claims]
    registry = ClaimRegistry(
        version=int(data.get("version", 1)),
        project=str(data.get("project", "")),
        entries=entries,
        conventions=data.get("conventions", {}) or {},
    )
    index: dict[str, str] = {}
    canonical_ids: set[str] = set()
    for entry in entries:
        if entry.id in canonical_ids:
            raise ValueError(f"Malformed claim registry: duplicate canonical ID {entry.id!r}")
        canonical_ids.add(entry.id)
        index[entry.id] = entry.id
        for syn in entry.synonyms:
            index.setdefault(syn, entry.id)
    return IndexedClaimRegistry(registry=registry, _index=index)


def _hydrate_entry(raw: dict[str, Any]) -> ClaimRegistryEntry:
    if not isinstance(raw, Mapping):
        raise ValueError("Malformed claim registry: each claim entry must be a mapping")
    claim_id = _required_str(raw, "id")
    source = _required_str(raw, "source")
    predicted_direction = _required_str(raw, "predicted_direction")
    return ClaimRegistryEntry(
        id=claim_id,
        source=source,
        definition=str(raw.get("definition", "")),
        predicted_direction=Token.from_str(predicted_direction),
        synonyms=_string_list(raw, "synonyms"),
        members=_string_list(raw, "members"),
        cited_in=_string_list(raw, "cited_in"),
    )


def _required_str(raw: Mapping[str, Any], field_name: str) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"Malformed claim registry: claim entry {field_name!r} is required")
    return value


def _string_list(raw: Mapping[str, Any], field_name: str) -> list[str]:
    value = raw.get(field_name, [])
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Malformed claim registry: claim entry {field_name!r} must be a list of strings")
    return value


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
