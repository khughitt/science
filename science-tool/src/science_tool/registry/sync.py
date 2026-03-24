"""Sync orchestrator for cross-project alignment and propagation."""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from science_tool.graph.sources import ProjectSources, SourceEntity, load_project_sources
from science_tool.registry.index import (
    RegistryEntity,
    RegistryEntitySource,
    RegistryIndex,
    load_registry_index,
    save_registry_index,
)
from science_tool.registry.propagation import compute_propagations, write_propagated_entity
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
    for path in project_paths:
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
    project_sources: dict[str, list[SourceEntity]],
) -> RegistryIndex:
    """Phase 2: Align entities across projects into the registry.

    project_sources maps project_name -> list of SourceEntity.
    """
    entity_map: dict[str, RegistryEntity] = {e.canonical_id: e for e in existing.entities}

    for project_name, entities in project_sources.items():
        today = date.today()
        for src in entities:
            if src.canonical_id in entity_map:
                entry = entity_map[src.canonical_id]
                _merge_aliases(entry, src.aliases)
                _merge_ontology_terms(entry, src.ontology_terms)
                _ensure_project_listed(entry, project_name, today)
            else:
                entity_map[src.canonical_id] = RegistryEntity(
                    canonical_id=src.canonical_id,
                    kind=src.kind,
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
    propagated: dict[str, int] = Field(default_factory=dict)  # "proj-a -> proj-b": count
    drift_warnings: list[str] = Field(default_factory=list)


def run_sync(
    *,
    project_paths: list[Path],
    registry_dir: Path,
    state_path: Path,
    dry_run: bool = False,
) -> SyncReport:
    """Execute full sync: collect -> align -> propagate -> save -> update state."""
    report = SyncReport()

    # Phase 1: Collect
    all_sources = collect_all_project_sources(project_paths=project_paths)
    if not all_sources:
        return report

    # Phase 2: Align
    existing_index = load_registry_index(registry_dir)
    old_count = len(existing_index.entities)

    project_entity_map: dict[str, list[SourceEntity]] = {}
    for sources in all_sources:
        project_entity_map[sources.project_name] = sources.entities

    new_index = align_registry(existing_index, project_entity_map)
    report.entities_total = len(new_index.entities)
    report.entities_new = len(new_index.entities) - old_count
    report.relations_total = len(new_index.relations)

    # Phase 3: Propagate
    shared = [e for e in new_index.entities if len(e.source_projects) >= 2]
    actions = compute_propagations(
        shared_entities=shared,
        project_sources=project_entity_map,
    )

    if not dry_run:
        name_to_root: dict[str, Path] = {s.project_name: Path(s.project_root) for s in all_sources}
        today = date.today()
        for action in actions:
            target_root = name_to_root.get(action.target_project)
            if target_root:
                write_propagated_entity(
                    entity=action.entity,
                    source_project=action.source_project,
                    target_project_root=target_root,
                    sync_date=today,
                )
                key = f"{action.source_project} -> {action.target_project}"
                report.propagated[key] = report.propagated.get(key, 0) + 1

        # Phase 4/5: Save registry and update state
        save_registry_index(new_index, registry_dir)

        now = datetime.now()
        state = SyncState(last_sync=now, projects={})
        for sources in all_sources:
            ids = [e.canonical_id for e in sources.entities]
            state.projects[sources.project_name] = ProjectSyncState(
                last_synced=now,
                entity_count=len(ids),
                entity_hash=compute_entity_hash(ids),
            )
        save_sync_state(state, state_path)

    return report
