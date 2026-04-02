"""Cross-project content propagation for sync."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel

from science_tool.graph.sources import SourceEntity

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
    shared_pairs: list[tuple[str, str, str, str]],  # (local_id_a, local_id_b, project_a, project_b)
    project_sources: dict[str, list[SourceEntity]],
    project_ontology_prefixes: dict[str, set[str]] | None = None,
) -> list[PropagationAction]:
    """Compute which entities should be propagated across projects.

    shared_pairs: each tuple (local_id_a, local_id_b, project_a, project_b) indicates
    that the two local IDs represent the same real-world entity across projects.

    project_ontology_prefixes: optional mapping of project_name -> set of ontology
    prefixes the project declares. When provided, entities with ontology_terms are
    only propagated to projects whose prefixes overlap. Entities without ontology_terms
    are propagated regardless (no filtering possible).
    """
    project_ids: dict[str, set[str]] = {
        name: {e.canonical_id for e in entities} for name, entities in project_sources.items()
    }

    # Build per-project lookup: local_id -> set of partner projects
    project_shared: dict[str, dict[str, set[str]]] = {}
    for local_id_a, local_id_b, proj_a, proj_b in shared_pairs:
        project_shared.setdefault(proj_a, {}).setdefault(local_id_a, set()).add(proj_b)
        project_shared.setdefault(proj_b, {}).setdefault(local_id_b, set()).add(proj_a)

    # Collect all shared local IDs for related-field checking
    all_shared_local_ids: set[str] = set()
    for local_id_a, local_id_b, _, _ in shared_pairs:
        all_shared_local_ids.add(local_id_a)
        all_shared_local_ids.add(local_id_b)

    actions: list[PropagationAction] = []

    for source_project, entities in project_sources.items():
        shared_in_project = project_shared.get(source_project, {})
        if not shared_in_project:
            continue

        for entity in entities:
            if not _is_propagatable(entity):
                continue

            # Check if entity references any shared local ID
            referenced_shared = all_shared_local_ids & set(entity.related)
            if not referenced_shared:
                continue

            # Find target projects
            target_projects: set[str] = set()
            for ref_id in referenced_shared:
                if ref_id in shared_in_project:
                    target_projects.update(shared_in_project[ref_id])

            for target_project in target_projects:
                if entity.canonical_id in project_ids.get(target_project, set()):
                    continue
                if not _ontology_relevant(entity, target_project, project_ontology_prefixes):
                    continue
                actions.append(
                    PropagationAction(
                        source_project=source_project,
                        target_project=target_project,
                        entity=entity,
                        shared_via=next(iter(referenced_shared)),
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


def _ontology_relevant(
    entity: SourceEntity,
    target_project: str,
    project_ontology_prefixes: dict[str, set[str]] | None,
) -> bool:
    """Check whether an entity is ontology-relevant to the target project.

    Returns True (allow propagation) when:
    - No prefix map is provided (filtering disabled)
    - The target project declares no ontologies (accepts everything)
    - The entity has no ontology_terms (can't filter, allow by default)
    - Any entity ontology_term prefix matches a target project prefix
    """
    if project_ontology_prefixes is None:
        return True
    target_prefixes = project_ontology_prefixes.get(target_project)
    if not target_prefixes:
        return True
    if not entity.ontology_terms:
        return True
    entity_prefixes = {term.split(":")[0].lower() for term in entity.ontology_terms if ":" in term}
    return bool(entity_prefixes & target_prefixes)


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
