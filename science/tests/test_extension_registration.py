"""Demonstrate and test the project-extension registration path for custom kinds."""

from __future__ import annotations

import pytest

from science_model.entities import ProjectEntity
from science_tool.graph.entity_registry import (
    EntityKindAlreadyRegisteredError,
    EntityKindNotRegisteredError,
    EntityKindShadowError,
    EntityRegistry,
)


class _NaturalSystemModel(ProjectEntity):
    """Example project-defined extension entity."""

    equation: str = ""
    parameters_list: list[str] = []


def test_extension_kind_registration_round_trip() -> None:
    r = EntityRegistry.with_core_types()
    r.register_extension_kind("natural-system:model", _NaturalSystemModel)
    resolved = r.resolve("natural-system:model")
    assert resolved is _NaturalSystemModel


def test_extension_cannot_shadow_core_kind() -> None:
    r = EntityRegistry.with_core_types()
    with pytest.raises(EntityKindShadowError, match="dataset"):
        r.register_extension_kind("dataset", _NaturalSystemModel)


def test_extension_duplicate_registration_rejected() -> None:
    class _Other(ProjectEntity):
        pass

    r = EntityRegistry.with_core_types()
    r.register_extension_kind("natural-system:model", _NaturalSystemModel)
    with pytest.raises(EntityKindAlreadyRegisteredError):
        r.register_extension_kind("natural-system:model", _Other)


def test_unknown_kind_without_registration_fails_fast() -> None:
    """Project kinds that are neither core nor registered as extensions fail fast."""
    r = EntityRegistry.with_core_types()
    with pytest.raises(EntityKindNotRegisteredError, match="unregistered-kind:x"):
        r.resolve("unregistered-kind:x")


def test_extension_entity_validates_through_registered_schema() -> None:
    """Pydantic validates an extension-registered class's fields at load time."""
    r = EntityRegistry.with_core_types()
    r.register_extension_kind("natural-system:model", _NaturalSystemModel)
    cls = r.resolve("natural-system:model")
    instance = cls.model_validate(
        {
            "id": "natural-system:model:example",
            "canonical_id": "natural-system:model:example",
            "kind": "natural-system:model",
            "type": None,
            "title": "Example model",
            "project": "demo",
            "ontology_terms": [],
            "related": [],
            "source_refs": [],
            "content_preview": "",
            "file_path": "knowledge/sources/local/models.yaml",
            "equation": "y = mx + b",
            "parameters_list": ["m", "b"],
        }
    )
    assert isinstance(instance, _NaturalSystemModel)
    assert isinstance(instance, ProjectEntity)
    assert instance.equation == "y = mx + b"
    assert instance.parameters_list == ["m", "b"]
