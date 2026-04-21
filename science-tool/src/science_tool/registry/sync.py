"""Sync orchestrator for cross-project alignment and propagation."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field
from science_model.entities import Entity

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
                _ensure_project_listed(entry, project_name, today)
            else:
                entity_map[registry_id] = RegistryEntity(
                    canonical_id=registry_id,
                    kind=src.type.value,
                    title=src.title,
                    profile=src.profile,
                    aliases=list(src.aliases),
                    ontology_terms=list(src.ontology_terms),
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


def _ensure_project_listed(entry: RegistryEntity, project_name: str, today: date) -> None:
    project_names = {sp.project for sp in entry.source_projects}
    if project_name not in project_names:
        entry.source_projects.append(RegistryEntitySource(project=project_name, first_seen=today))


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
