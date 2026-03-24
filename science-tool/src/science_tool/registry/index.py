"""Registry entity and relation index for cross-project sync."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from science_tool.registry.config import SCIENCE_CONFIG_DIR

DEFAULT_REGISTRY_DIR = SCIENCE_CONFIG_DIR / "registry"


class RegistryEntitySource(BaseModel):
    """Per-project presence record in the registry."""

    project: str
    status: str | None = None
    first_seen: date


class RegistryEntity(BaseModel):
    """An entity tracked across projects in the registry."""

    canonical_id: str
    kind: str
    title: str
    profile: str
    aliases: list[str] = Field(default_factory=list)
    ontology_terms: list[str] = Field(default_factory=list)
    source_projects: list[RegistryEntitySource] = Field(default_factory=list)


class RegistryRelation(BaseModel):
    """A relation tracked across projects in the registry."""

    subject: str
    predicate: str
    object: str
    graph_layer: str = "graph/knowledge"
    source_projects: list[str] = Field(default_factory=list)


class RegistryIndex(BaseModel):
    """The complete registry index (entities + relations)."""

    entities: list[RegistryEntity] = Field(default_factory=list)
    relations: list[RegistryRelation] = Field(default_factory=list)


def load_registry_index(registry_dir: Path = DEFAULT_REGISTRY_DIR) -> RegistryIndex:
    """Load entity and relation indices from the registry directory."""
    entities: list[RegistryEntity] = []
    relations: list[RegistryRelation] = []

    entities_path = registry_dir / "entities.yaml"
    if entities_path.is_file():
        data = yaml.safe_load(entities_path.read_text(encoding="utf-8")) or {}
        for item in data.get("entities") or []:
            if isinstance(item, dict):
                entities.append(RegistryEntity.model_validate(item))

    relations_path = registry_dir / "relations.yaml"
    if relations_path.is_file():
        data = yaml.safe_load(relations_path.read_text(encoding="utf-8")) or {}
        for item in data.get("relations") or []:
            if isinstance(item, dict):
                relations.append(RegistryRelation.model_validate(item))

    return RegistryIndex(entities=entities, relations=relations)


def save_registry_index(index: RegistryIndex, registry_dir: Path = DEFAULT_REGISTRY_DIR) -> None:
    """Save entity and relation indices to the registry directory."""
    registry_dir.mkdir(parents=True, exist_ok=True)

    entities_data = {"entities": [e.model_dump(mode="json") for e in index.entities]}
    (registry_dir / "entities.yaml").write_text(
        yaml.dump(entities_data, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )

    relations_data = {"relations": [r.model_dump(mode="json") for r in index.relations]}
    (registry_dir / "relations.yaml").write_text(
        yaml.dump(relations_data, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )
