"""Tests for EntityRegistry — kind → schema dispatch per spec §Model Registry."""

from __future__ import annotations

import pytest

from science_model.entities import (
    DatasetEntity,
    Entity,
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


def test_generic_kinds_default_to_project_entity() -> None:
    """Kinds without a dedicated typed entity (concept, hypothesis, topic, question, paper…)
    are registered against ProjectEntity so generic tooling still works."""
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("concept") is ProjectEntity
    assert registry.resolve("hypothesis") is ProjectEntity
    assert registry.resolve("topic") is ProjectEntity


def test_unknown_kind_raises() -> None:
    registry = EntityRegistry.with_core_types()
    with pytest.raises(EntityKindNotRegisteredError, match="frobnicator"):
        registry.resolve("frobnicator")


def test_duplicate_core_registration_is_hard_error() -> None:
    registry = EntityRegistry.with_core_types()
    with pytest.raises(EntityKindAlreadyRegisteredError):
        registry.register_core_kind("task", TaskEntity)


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


def test_resolve_round_trip_extension() -> None:
    class CustomModelEntity(ProjectEntity):
        equation: str = ""

    registry = EntityRegistry.with_core_types()
    registry.register_extension_kind("natural-system:model", CustomModelEntity)
    assert registry.resolve("natural-system:model") is CustomModelEntity


def test_registered_class_must_subclass_entity() -> None:
    class NotAnEntity:
        pass

    registry = EntityRegistry()
    with pytest.raises(TypeError, match="must subclass Entity"):
        registry.register_core_kind("x", NotAnEntity)  # type: ignore[arg-type]
