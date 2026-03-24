"""Cross-project content propagation for sync."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel

from science_tool.graph.sources import SourceEntity
from science_tool.registry.index import RegistryEntity

# Entity kinds eligible for propagation
_ALWAYS_PROPAGATE = frozenset({"question", "claim", "relation_claim", "hypothesis", "evidence"})
_TAG_PROPAGATE = frozenset({"task", "dataset", "method"})


class PropagationAction(BaseModel):
    """A pending propagation of an entity from one project to another."""

    source_project: str
    target_project: str
    entity: SourceEntity
    shared_via: str  # canonical_id of the shared entity that triggered propagation


def compute_propagations(
    *,
    shared_entities: list[RegistryEntity],
    project_sources: dict[str, list[SourceEntity]],
) -> list[PropagationAction]:
    """Compute which entities should be propagated across projects."""
    # Build lookup: project -> set of canonical_ids
    project_ids: dict[str, set[str]] = {
        name: {e.canonical_id for e in entities} for name, entities in project_sources.items()
    }

    actions: list[PropagationAction] = []

    for shared in shared_entities:
        shared_project_names = {sp.project for sp in shared.source_projects}
        if len(shared_project_names) < 2:
            continue

        for source_project, entities in project_sources.items():
            if source_project not in shared_project_names:
                continue

            for entity in entities:
                if not _is_propagatable(entity):
                    continue
                if shared.canonical_id not in entity.related:
                    continue

                for target_project in shared_project_names:
                    if target_project == source_project:
                        continue
                    if entity.canonical_id in project_ids.get(target_project, set()):
                        continue
                    actions.append(
                        PropagationAction(
                            source_project=source_project,
                            target_project=target_project,
                            entity=entity,
                            shared_via=shared.canonical_id,
                        )
                    )

    return actions


def write_propagated_entity(
    *,
    entity: SourceEntity,
    source_project: str,
    target_project_root: Path,
    sync_date: date,
) -> Path:
    """Write a propagated entity as a markdown file in doc/sync/."""
    sync_dir = target_project_root / "doc" / "sync"
    sync_dir.mkdir(parents=True, exist_ok=True)

    slug = entity.canonical_id.replace(":", "-").replace("/", "-")
    filename = f"{slug}-from-{source_project}.md"
    output_path = sync_dir / filename

    related_yaml = "\n".join(f'  - "{r}"' for r in entity.related) if entity.related else "  []"
    content = (
        f"---\n"
        f'id: "{entity.canonical_id}"\n'
        f"type: {entity.kind}\n"
        f'title: "{entity.title}"\n'
        f"status: open\n"
        f"tags: [sync-propagated]\n"
        f"related:\n{related_yaml}\n"
        f"source_refs: []\n"
        f"sync_source:\n"
        f'  project: "{source_project}"\n'
        f'  entity_id: "{entity.canonical_id}"\n'
        f'  sync_date: "{sync_date.isoformat()}"\n'
        f"---\n"
        f"\n"
        f"*Propagated from {source_project} on {sync_date.isoformat()}.*\n"
        f"\n"
        f"{entity.content_preview}\n"
    )
    output_path.write_text(content, encoding="utf-8")
    return output_path


def _is_propagatable(entity: SourceEntity) -> bool:
    """Check if an entity is eligible for propagation."""
    # Never re-propagate sync-sourced entities (prevents A->B->A storms)
    if "sync-propagated" in entity.tags:
        return False
    if entity.source_path.startswith("doc/sync/"):
        return False

    if entity.kind in _ALWAYS_PROPAGATE:
        return True
    if entity.kind in _TAG_PROPAGATE:
        return "cross-project" in entity.tags
    return False
