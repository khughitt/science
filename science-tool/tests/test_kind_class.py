"""Tests for EntityRegistry's entity_class classification."""

from __future__ import annotations

import pytest

from science_model.entities import EntityClass, ProjectEntity
from science_tool.graph.entity_registry import EntityRegistry


def test_with_core_types_classifies_every_kind():
    """Every kind registered by with_core_types() must have a classification."""
    r = EntityRegistry.with_core_types()
    classifications = r.all_kind_classes()
    # Spot-check a representative sample of each class.
    assert classifications["hypothesis"] == EntityClass.EPISTEMIC
    assert classifications["proposition"] == EntityClass.EPISTEMIC
    assert classifications["observation"] == EntityClass.EPISTEMIC
    assert classifications["finding"] == EntityClass.EPISTEMIC
    assert classifications["interpretation"] == EntityClass.EPISTEMIC
    assert classifications["discussion"] == EntityClass.EPISTEMIC
    assert classifications["story"] == EntityClass.EPISTEMIC
    assert classifications["mechanism"] == EntityClass.EPISTEMIC

    assert classifications["task"] == EntityClass.OPERATIONAL
    assert classifications["dataset"] == EntityClass.OPERATIONAL
    assert classifications["workflow"] == EntityClass.OPERATIONAL
    assert classifications["workflow-run"] == EntityClass.OPERATIONAL
    assert classifications["workflow-step"] == EntityClass.OPERATIONAL
    assert classifications["data-package"] == EntityClass.OPERATIONAL
    assert classifications["research-package"] == EntityClass.OPERATIONAL
    assert classifications["paper"] == EntityClass.OPERATIONAL
    assert classifications["plan"] == EntityClass.OPERATIONAL

    assert classifications["concept"] == EntityClass.REFERENCE
    assert classifications["topic"] == EntityClass.REFERENCE
    assert classifications["article"] == EntityClass.REFERENCE
    assert classifications["variable"] == EntityClass.REFERENCE
    assert classifications["inquiry"] == EntityClass.REFERENCE


def test_kind_class_lookup_returns_classification():
    r = EntityRegistry.with_core_types()
    assert r.kind_class("hypothesis") == EntityClass.EPISTEMIC
    assert r.kind_class("dataset") == EntityClass.OPERATIONAL
    assert r.kind_class("article") == EntityClass.REFERENCE


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


def test_register_core_kind_requires_entity_class():
    r = EntityRegistry()

    class MyEntity(ProjectEntity):
        pass

    # Calling without entity_class should raise TypeError (missing required kwarg).
    with pytest.raises(TypeError):
        r.register_core_kind("foo", MyEntity)  # type: ignore[call-arg]
