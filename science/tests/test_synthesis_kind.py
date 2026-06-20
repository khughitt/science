from __future__ import annotations

from science_model.entities import EntityClass

from science_tool.graph.entity_registry import EntityRegistry


def test_synthesis_is_registered_epistemic() -> None:
    registry = EntityRegistry.with_core_types()
    classes = registry.all_kind_classes()
    assert "synthesis" in classes
    assert classes["synthesis"] == EntityClass.EPISTEMIC


def test_report_remains_epistemic() -> None:
    registry = EntityRegistry.with_core_types()
    assert registry.all_kind_classes()["report"] == EntityClass.EPISTEMIC
