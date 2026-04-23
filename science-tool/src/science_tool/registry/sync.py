"""Sync orchestrator for cross-project alignment and propagation."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field
from science_model.entities import Entity
from science_model.identity import EntityScope

from science_tool.graph.sources import ProjectSources, load_project_sources
from science_tool.registry.index import (
    RegistryEntity,
    RegistryEntitySource,
    RegistryIndex,
    load_registry_index,
    save_registry_index,
)
from science_tool.registry.state import (
    ProjectSyncState,
    SyncState,
    compute_entity_hash,
    save_sync_state,
)

logger = logging.getLogger(__name__)


def collect_all_project_sources(
    *,
    project_paths: list[Path],
) -> list[ProjectSources]:
    """Phase 1: Load sources for each registered project, skipping missing."""
    results: list[ProjectSources] = []
    for raw_path in project_paths:
        path = raw_path.expanduser().resolve()
        if not path.is_dir() or not (path / "science.yaml").is_file():
            logger.warning("Skipping missing project at %s", path)
            continue
        try:
            sources = load_project_sources(path)
            results.append(sources)
        except Exception:
            logger.warning("Failed to load project at %s", path, exc_info=True)
    return results


def align_registry(
    existing: RegistryIndex,
    project_sources: Mapping[str, Sequence[Entity]],
) -> RegistryIndex:
    """Phase 2: Align entities across projects into the registry.

    project_sources maps project_name -> list of Entity.
    Registry keys are namespaced as ``project_name::canonical_id`` to prevent
    false deduplication of sequential IDs across unrelated projects.
    """
    for project_name in project_sources:
        if "::" in project_name:
            raise ValueError(f"Project name must not contain '::': {project_name!r}")

    entity_map: dict[str, RegistryEntity] = {e.canonical_id: e for e in existing.entities}

    for project_name, entities in project_sources.items():
        today = date.today()
        for src in entities:
            registry_id = f"{project_name}::{src.canonical_id}"
            if registry_id in entity_map:
                entry = entity_map[registry_id]
                _merge_aliases(entry, src.aliases)
                _merge_ontology_terms(entry, src.ontology_terms)
                _merge_identity_metadata(entry, src)
                _ensure_project_listed(entry, project_name, today)
            else:
                entity_map[registry_id] = RegistryEntity(
                    canonical_id=registry_id,
                    kind=src.kind,
                    title=src.title,
                    profile=src.profile,
                    scope=src.scope,
                    primary_external_id=src.primary_external_id,
                    aliases=list(src.aliases),
                    ontology_terms=list(src.ontology_terms),
                    deprecated_ids=list(src.deprecated_ids),
                    taxon=src.taxon,
                    source_projects=[
                        RegistryEntitySource(project=project_name, first_seen=today),
                    ],
                )

    entities = sorted(entity_map.values(), key=lambda e: e.canonical_id)
    return RegistryIndex(entities=entities, relations=existing.relations)


def _merge_aliases(entry: RegistryEntity, new_aliases: list[str]) -> None:
    existing = set(entry.aliases)
    for alias in new_aliases:
        if alias not in existing:
            entry.aliases.append(alias)
            existing.add(alias)


def _merge_ontology_terms(entry: RegistryEntity, new_terms: list[str]) -> None:
    existing = set(entry.ontology_terms)
    for term in new_terms:
        if term not in existing:
            entry.ontology_terms.append(term)
            existing.add(term)


def _merge_identity_metadata(entry: RegistryEntity, src: Entity) -> None:
    if entry.scope != src.scope:
        entry.scope = src.scope
    if src.primary_external_id is not None:
        entry.primary_external_id = src.primary_external_id
    if src.deprecated_ids:
        existing = set(entry.deprecated_ids)
        for deprecated_id in src.deprecated_ids:
            if deprecated_id not in existing:
                entry.deprecated_ids.append(deprecated_id)
                existing.add(deprecated_id)
    if src.taxon is not None:
        entry.taxon = src.taxon


def _ensure_project_listed(entry: RegistryEntity, project_name: str, today: date) -> None:
    project_names = {sp.project for sp in entry.source_projects}
    if project_name not in project_names:
        entry.source_projects.append(RegistryEntitySource(project=project_name, first_seen=today))


def _collect_identity_drift_warnings(index: RegistryIndex) -> list[str]:
    warnings: list[str] = []

    by_bare_id: dict[str, list[RegistryEntity]] = defaultdict(list)
    by_primary_external_id: dict[str, list[RegistryEntity]] = defaultdict(list)
    for entry in index.entities:
        by_bare_id[_bare_registry_id(entry.canonical_id)].append(entry)
        if entry.primary_external_id is not None:
            by_primary_external_id[entry.primary_external_id.curie].append(entry)

    for bare_id, entries in sorted(by_bare_id.items()):
        if len(entries) < 2:
            continue
        if any(entry.scope == EntityScope.PROJECT for entry in entries):
            registry_ids = ", ".join(sorted(entry.canonical_id for entry in entries))
            warnings.append(f"canonical_id collision for {bare_id}: {registry_ids}")
            continue
        if _shared_identity_signature(entries) is not None:
            continue
        registry_ids = ", ".join(sorted(entry.canonical_id for entry in entries))
        warnings.append(f"incompatible shared metadata for {bare_id}: {registry_ids}")

    for curie, entries in sorted(by_primary_external_id.items()):
        distinct_registry_ids = sorted({entry.canonical_id for entry in entries})
        if len(distinct_registry_ids) < 2:
            continue
        warnings.append(f"primary_external_id collision for {curie}: {', '.join(distinct_registry_ids)}")

    return warnings


def _shared_identity_signature(entries: list[RegistryEntity]) -> tuple[tuple[str, str | None, str | None, str | None], ...] | None:
    signatures = {
        (
            entry.kind,
            entry.primary_external_id.curie if entry.primary_external_id is not None else None,
            entry.taxon,
            entry.scope.value,
        )
        for entry in entries
    }
    if len(signatures) == 1:
        return tuple(sorted(signatures))
    return None


def _bare_registry_id(canonical_id: str) -> str:
    if "::" not in canonical_id:
        return canonical_id
    return canonical_id.split("::", 1)[1]


class SyncReport(BaseModel):
    """Summary of a sync run."""

    entities_total: int = 0
    entities_new: int = 0
    relations_total: int = 0
    drift_warnings: list[str] = Field(default_factory=list)


def run_sync(
    *,
    project_paths: list[Path],
    registry_dir: Path,
    state_path: Path,
    dry_run: bool = False,
) -> SyncReport:
    """Execute full sync: collect -> align -> save -> update state.

    Registry-only sync: builds a cross-project entity index without
    propagating content between projects.
    """
    report = SyncReport()

    # Phase 1: Collect
    all_sources = collect_all_project_sources(project_paths=project_paths)
    if not all_sources:
        return report

    # Phase 2: Align
    existing_index = load_registry_index(registry_dir)
    old_count = len(existing_index.entities)

    project_entity_map: dict[str, list[Entity]] = {}
    for sources in all_sources:
        project_entity_map[sources.project_name] = sources.entities

    new_index = align_registry(existing_index, project_entity_map)
    report.entities_total = len(new_index.entities)
    report.entities_new = len(new_index.entities) - old_count
    report.relations_total = len(new_index.relations)
    report.drift_warnings = _collect_identity_drift_warnings(new_index)

    if not dry_run:
        save_registry_index(new_index, registry_dir)

        now = datetime.now()
        state = SyncState(last_sync=now, projects={})
        for sources in all_sources:
            ids = [f"{sources.project_name}::{e.canonical_id}" for e in sources.entities]
            state.projects[sources.project_name] = ProjectSyncState(
                last_synced=now,
                entity_count=len(ids),
                entity_hash=compute_entity_hash(ids),
            )
        save_sync_state(state, state_path)

    return report
