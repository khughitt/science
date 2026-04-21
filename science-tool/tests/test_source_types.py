"""Tests for graph.source_types — the neutral home for SourceEntity, SourceRelation, etc."""

from __future__ import annotations


def test_source_types_module_exposes_canonical_types() -> None:
    """The new neutral module exports the types the entity_providers package needs."""
    from science_tool.graph.source_types import (
        EntityIdCollisionError,
        EntityDatapackageInvalidError,
        KnowledgeProfiles,  # noqa: F401
        SourceEntity,  # noqa: F401
        SourceRelation,  # noqa: F401
    )

    # Smoke check: exported symbols are real classes
    assert isinstance(EntityIdCollisionError, type)
    assert isinstance(EntityDatapackageInvalidError, type)
    assert issubclass(EntityIdCollisionError, ValueError)
    assert issubclass(EntityDatapackageInvalidError, ValueError)


def test_sources_module_re_exports_for_back_compat() -> None:
    """Existing consumers `from science_tool.graph.sources import SourceEntity` continue to work."""
    from science_tool.graph.sources import SourceEntity as SourceEntityFromSources
    from science_tool.graph.source_types import SourceEntity as SourceEntityFromTypes

    assert SourceEntityFromSources is SourceEntityFromTypes


def test_entity_id_collision_error_message_includes_sources() -> None:
    from science_tool.graph.source_types import EntityIdCollisionError

    err = EntityIdCollisionError("dataset:x", [("markdown", "doc/datasets/x.md"), ("aggregate", "entities.yaml")])
    msg = str(err)
    assert "dataset:x" in msg
    assert "markdown" in msg
    assert "doc/datasets/x.md" in msg
    assert "aggregate" in msg
    assert "entities.yaml" in msg


def test_entity_datapackage_invalid_error_message_includes_path_and_field() -> None:
    from science_tool.graph.source_types import EntityDatapackageInvalidError

    err = EntityDatapackageInvalidError("data/x/datapackage.yaml", "missing required entity field 'id'")
    msg = str(err)
    assert "data/x/datapackage.yaml" in msg
    assert "missing required entity field 'id'" in msg
