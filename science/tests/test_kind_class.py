"""Tests for EntityRegistry's entity_class classification."""

from __future__ import annotations

import pytest

from science_model.entities import EntityClass, ProjectEntity
from science_tool.graph.entity_registry import EntityRegistry


def test_with_core_types_classifies_every_kind():
    """Every kind registered by with_core_types() must have a classification
    matching the source-of-truth _CORE_KIND_CLASSES dict. Exhaustive equality
    check rather than spot-check, so dropping or re-classifying any kind fails
    loudly."""
    from science_tool.graph.entity_registry import _CORE_KIND_CLASSES

    r = EntityRegistry.with_core_types()
    classifications = r.all_kind_classes()
    assert set(classifications) == set(_CORE_KIND_CLASSES), (
        f"missing: {set(_CORE_KIND_CLASSES) - set(classifications)}, "
        f"extra: {set(classifications) - set(_CORE_KIND_CLASSES)}"
    )
    for kind, expected in _CORE_KIND_CLASSES.items():
        assert classifications[kind] == expected, kind


def test_kind_class_lookup_returns_classification():
    r = EntityRegistry.with_core_types()
    assert r.kind_class("hypothesis") == EntityClass.EPISTEMIC
    assert r.kind_class("dataset") == EntityClass.OPERATIONAL
    assert r.kind_class("article") == EntityClass.REFERENCE
    assert r.kind_class("theme") == EntityClass.EPISTEMIC


def test_kind_class_lookup_for_unknown_kind_raises():
    from science_tool.graph.entity_registry import EntityKindNotRegisteredError

    r = EntityRegistry.with_core_types()
    with pytest.raises(EntityKindNotRegisteredError):
        r.kind_class("frobnicator")


def test_register_extension_kind_defaults_to_operational():
    r = EntityRegistry.with_core_types()

    class MyExt(ProjectEntity):
        pass

    r.register_extension_kind("nat-sys:species", MyExt)
    assert r.kind_class("nat-sys:species") == EntityClass.OPERATIONAL


def test_register_extension_kind_accepts_explicit_class():
    r = EntityRegistry.with_core_types()

    class MyExt(ProjectEntity):
        pass

    r.register_extension_kind("nat-sys:eco-claim", MyExt, entity_class=EntityClass.EPISTEMIC)
    assert r.kind_class("nat-sys:eco-claim") == EntityClass.EPISTEMIC


def test_register_profile_kind_defaults_to_operational():
    r = EntityRegistry()

    class MyProfileEntity(ProjectEntity):
        pass

    r.register_profile_kind("local:thing", MyProfileEntity, owner="local")
    assert r.kind_class("local:thing") == EntityClass.OPERATIONAL


def test_register_catalog_kind_defaults_to_reference():
    from science_model.entities import DomainEntity

    r = EntityRegistry()

    class MyCatalogEntity(DomainEntity):
        pass

    r.register_catalog_kind("biology:gene-mock", MyCatalogEntity, owner="biology")
    assert r.kind_class("biology:gene-mock") == EntityClass.REFERENCE


def test_register_core_kind_requires_entity_class():
    r = EntityRegistry()

    class MyEntity(ProjectEntity):
        pass

    # Calling without entity_class should raise TypeError (missing required kwarg).
    with pytest.raises(TypeError):
        r.register_core_kind("foo", MyEntity)  # type: ignore[call-arg]
