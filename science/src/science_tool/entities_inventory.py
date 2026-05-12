from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from science_model import Entity
from science_model.contracts.inventory_v1 import (
    InventoryAlias,
    InventoryEntity,
    InventoryPayload,
    InventoryProjectMetadata,
    InventoryWarning,
    InventoryReference,
    InventorySourceLocation,
    finalize_inventory_payload,
)

from science_tool.dag.inventory import load_dag_inventory_records
from science_tool.entity_identity import collect_identity_warnings
from science_tool.graph.sources import load_project_sources

DEFAULT_WATCH_PATHS = ["doc", "knowledge", "notes", "papers", "results", "specs", "tasks"]
PROMOTED_ENTITY_DATA_FIELDS = {
    "id",
    "canonical_id",
    "kind",
    "type",
    "title",
    "status",
    "project",
    "ontology_terms",
    "related",
    "relations",
    "source_refs",
    "aliases",
    "deprecated_ids",
    "review_state",
    "file_path",
    "scope",
    "targets",
}


def build_inventory(project_root: Path) -> InventoryPayload:
    project_root = project_root.resolve()
    sources = load_project_sources(project_root)
    dag_records = load_dag_inventory_records(project_root)
    project_metadata = _read_project_metadata(project_root)
    warnings: list[InventoryWarning] = [*collect_identity_warnings(project_root, sources=sources), *dag_records.warnings]

    entities: list[InventoryEntity] = []
    aliases: list[InventoryAlias] = []
    ontology_profile_names = {catalog.ontology for catalog in sources.ontology_catalogs}

    for entity in sorted(sources.entities, key=lambda item: item.canonical_id or item.id):
        canonical_id = entity.canonical_id or entity.id
        kind = entity.kind
        local_id = canonical_id.split(":", 1)[1] if ":" in canonical_id else canonical_id
        adapter = sources.entity_source_adapters.get(canonical_id)
        if adapter is None:
            raise ValueError(f"Entity {canonical_id} is missing source adapter mapping.")
        source = InventorySourceLocation(
            adapter=adapter,
            path=entity.file_path,
        )
        entity_data = entity.model_dump(mode="json", exclude_none=True, exclude=set())
        data = {key: value for key, value in entity_data.items() if key not in PROMOTED_ENTITY_DATA_FIELDS}
        entities.append(
            InventoryEntity(
                id=canonical_id,
                kind=kind,
                local_id=local_id,
                title=entity.title,
                status=entity.status,
                registration_state=_registration_state(entity, ontology_profile_names=ontology_profile_names),
                scope=_inventory_scope(entity),
                source=source,
                aliases=list(entity.aliases),
                related=_references_from_entity(entity),
                source_refs=list(entity.source_refs),
                targets=[str(value) for value in entity_data.get("targets", []) if value],
                review_state=_optional_str(entity.review_state),
                deprecated_ids=list(entity.deprecated_ids),
                data=data,
            )
        )
        aliases.extend(InventoryAlias(alias=alias, canonical_id=canonical_id) for alias in entity.aliases)

    payload = InventoryPayload(
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        project_id=project_metadata.id,
        project_path=project_root.as_posix(),
        project=project_metadata,
        entities=entities,
        aliases=sorted(aliases, key=lambda item: item.alias),
        graph_addresses=dag_records.graph_addresses,
        finding_candidates=dag_records.finding_candidates,
        warnings=warnings,
        watch_paths=_watch_paths(project_root),
    )
    return finalize_inventory_payload(payload)


def _read_project_metadata(project_root: Path) -> InventoryProjectMetadata:
    config_path = project_root / "science.yaml"
    if not config_path.exists():
        return InventoryProjectMetadata(id=project_root.name, name=project_root.name, path=project_root.as_posix())
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    project_id = data.get("id")
    canonical_id = str(project_id) if project_id else project_root.name
    return InventoryProjectMetadata(
        id=canonical_id,
        name=str(data.get("name") or project_root.name),
        path=str(data.get("path") or project_root.as_posix()),
        summary=_optional_str(data.get("summary")),
        status=_optional_str(data.get("status")),
        aspects=[str(value) for value in data.get("aspects", [])],
        tags=[str(value) for value in data.get("tags", [])],
    )


def _watch_paths(project_root: Path) -> list[str]:
    return [path for path in DEFAULT_WATCH_PATHS if (project_root / path).exists()]


def _references_from_entity(entity: Entity) -> list[InventoryReference]:
    return [InventoryReference(relation="related", target_id=target) for target in entity.related]


def _registration_state(
    entity: Entity, *, ontology_profile_names: set[str]
) -> Literal["core", "ontology", "local", "unknown"]:
    if entity.profile == "core":
        return "core"
    if entity.profile in ontology_profile_names:
        return "ontology"
    if entity.profile:
        return "local"
    return "unknown"


def _inventory_scope(entity: Entity) -> Literal["project", "cross-project"]:
    if str(entity.scope) == "shared":
        return "cross-project"
    return "project"


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None
