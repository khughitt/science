"""Tests for the entity model family: Entity → ProjectEntity / DomainEntity.

Per the unified-entity-model spec §Entity Subfamilies, ProjectEntity and
DomainEntity are semantic sub-bases under Entity. Typed entities (TaskEntity,
DatasetEntity, etc.) extend ProjectEntity and are added in Task 2.

Note (controller directive): field relocation off base Entity is deferred to
a post-plan cleanup. This task only adds the new subclasses; fields stay on
base Entity for compatibility with existing call sites. Invariants are
enforced via @model_validator on typed subclasses in Task 2.
"""

from __future__ import annotations

from science_model.entities import DomainEntity, Entity, EntityType, ProjectEntity


def _minimal_entity_kwargs(kind: EntityType, id_: str) -> dict:
    """Shared minimal arg set for Entity-like construction."""
    return {
        "id": id_,
        "canonical_id": id_,
        "type": kind,
        "title": id_,
        "project": "demo",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": f"{id_}.md",
    }


def test_project_entity_inherits_from_entity() -> None:
    pe = ProjectEntity(**_minimal_entity_kwargs(EntityType.HYPOTHESIS, "hypothesis:h01"))
    assert isinstance(pe, Entity)
    assert pe.canonical_id == "hypothesis:h01"


def test_domain_entity_inherits_from_entity() -> None:
    de = DomainEntity(**_minimal_entity_kwargs(EntityType.UNKNOWN, "disease:DOID:0001"))
    assert isinstance(de, Entity)
    assert de.canonical_id == "disease:DOID:0001"


def test_project_entity_is_subclass_of_entity() -> None:
    assert issubclass(ProjectEntity, Entity)


def test_domain_entity_is_subclass_of_entity() -> None:
    assert issubclass(DomainEntity, Entity)


def test_project_and_domain_entity_are_siblings() -> None:
    """Neither subclasses the other; both subclass Entity directly."""
    assert not issubclass(ProjectEntity, DomainEntity)
    assert not issubclass(DomainEntity, ProjectEntity)
