"""Tests for EntityRegistry — kind → schema dispatch per spec §Model Registry."""

from __future__ import annotations

import pytest

from science_model.entities import (
    DatasetEntity,
    DomainEntity,
    EntityClass,
    EvidenceLineEntity,
    MechanismEntity,
    PaperEntity,
    ProjectEntity,
    TaskEntity,
)
from science_tool.graph.entity_registry import (
    EntityRegistry,
    EntityKindShadowError,
    EntityKindAlreadyRegisteredError,
    EntityKindNotRegisteredError,
)


def test_with_core_types_registers_all_core_kinds() -> None:
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("task") is TaskEntity
    assert registry.resolve("dataset") is DatasetEntity
    assert registry.resolve("workflow-run").__name__ == "WorkflowRunEntity"
    assert registry.resolve("research-package").__name__ == "ResearchPackageEntity"
    assert registry.resolve("paper") is PaperEntity


def test_generic_kinds_default_to_project_entity() -> None:
    """Kinds without a dedicated typed entity (concept, hypothesis, topic, question...)
    are registered against ProjectEntity so generic tooling still works."""
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("concept") is ProjectEntity
    assert registry.resolve("hypothesis") is ProjectEntity
    assert registry.resolve("topic") is ProjectEntity


def test_curation_sweep_kind_registered() -> None:
    """fb-2026-05-01-007: curation-sweep ledgers must resolve so health/inventory
    don't emit skip-noise on every run."""
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("curation-sweep") is ProjectEntity


def test_pre_registration_kind_registered_as_operational() -> None:
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("pre-registration") is ProjectEntity
    assert registry.kind_class("pre-registration") == EntityClass.OPERATIONAL


def test_inquiry_kind_is_epistemic() -> None:
    registry = EntityRegistry.with_core_types()
    assert registry.kind_class("inquiry") == EntityClass.EPISTEMIC


def test_research_question_kind_registered() -> None:
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("research-question") is ProjectEntity
    assert registry.kind_class("research-question") == EntityClass.EPISTEMIC


def test_mechanism_kind_resolves_to_typed_entity() -> None:
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("mechanism") is MechanismEntity


def test_unknown_kind_raises() -> None:
    registry = EntityRegistry.with_core_types()
    with pytest.raises(EntityKindNotRegisteredError, match="frobnicator"):
        registry.resolve("frobnicator")


def test_duplicate_core_registration_is_hard_error() -> None:
    registry = EntityRegistry.with_core_types()
    with pytest.raises(EntityKindAlreadyRegisteredError):
        registry.register_core_kind("task", TaskEntity, entity_class=EntityClass.OPERATIONAL)


def test_duplicate_extension_registration_is_hard_error() -> None:
    class ProjectExtA(ProjectEntity):
        pass

    class ProjectExtB(ProjectEntity):
        pass

    registry = EntityRegistry.with_core_types()
    registry.register_extension_kind("natural-system:model", ProjectExtA)
    with pytest.raises(EntityKindAlreadyRegisteredError):
        registry.register_extension_kind("natural-system:model", ProjectExtB)


def test_extension_cannot_shadow_core() -> None:
    class BogusDataset(ProjectEntity):
        pass

    registry = EntityRegistry.with_core_types()
    with pytest.raises(EntityKindShadowError, match="dataset"):
        registry.register_extension_kind("dataset", BogusDataset)


def test_profile_kind_registration_resolves() -> None:
    registry = EntityRegistry.with_core_types()
    registry.register_profile_kind("model", ProjectEntity, owner="local")
    assert registry.resolve("model") is ProjectEntity


def test_declared_catalog_kind_resolves_to_domain_entity() -> None:
    registry = EntityRegistry.with_core_types()
    registry.register_catalog_kind("gene", DomainEntity, owner="biology")
    assert registry.resolve("gene") is DomainEntity


def test_duplicate_catalog_kind_registration_is_allowed_when_schema_matches() -> None:
    registry = EntityRegistry.with_core_types()
    registry.register_catalog_kind("electric_field", DomainEntity, owner="physics")
    registry.register_catalog_kind("electric_field", DomainEntity, owner="units")

    assert registry.resolve("electric_field") is DomainEntity


def test_extension_cannot_shadow_catalog_kind() -> None:
    registry = EntityRegistry.with_core_types()
    registry.register_catalog_kind("gene", DomainEntity, owner="biology")
    with pytest.raises(EntityKindShadowError, match="gene"):
        registry.register_extension_kind("gene", ProjectEntity)


def test_resolve_round_trip_extension() -> None:
    class CustomModelEntity(ProjectEntity):
        equation: str = ""

    registry = EntityRegistry.with_core_types()
    registry.register_extension_kind("natural-system:model", CustomModelEntity)
    assert registry.resolve("natural-system:model") is CustomModelEntity


def test_evidence_line_kind_resolves_to_typed_entity() -> None:
    """evidence-line must be registered as a typed EPISTEMIC entity in the core registry."""
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("evidence-line") is EvidenceLineEntity
    assert registry.kind_class("evidence-line") == EntityClass.EPISTEMIC


def test_registered_class_must_subclass_entity() -> None:
    class NotAnEntity:
        pass

    registry = EntityRegistry()
    with pytest.raises(TypeError, match="must subclass Entity"):
        registry.register_core_kind("x", NotAnEntity, entity_class=EntityClass.OPERATIONAL)  # type: ignore[arg-type]


def test_core_registry_resolves_patch_definition() -> None:
    from science_model.entities import EntityClass
    from science_model.patch_definition import PatchDefinitionEntity
    from science_tool.graph.entity_registry import EntityRegistry

    registry = EntityRegistry.with_core_types()

    assert registry.resolve("patch-definition") is PatchDefinitionEntity
    assert registry.kind_class("patch-definition") is EntityClass.EPISTEMIC
