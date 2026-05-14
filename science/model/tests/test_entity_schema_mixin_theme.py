from __future__ import annotations

import pytest

from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+theme/1.0",
        "id": "theme:homology-aware-evaluation",
        "type": "theme",
        "title": "Homology-aware evaluation",
        "version": "1.0.0",
        "status": "active",
        "theme_kind": "methodological",
        "theme_scope": "cross-project",
        "created": "2026-05-13",
        "updated": "2026-05-13",
    }


def test_theme_minimal_validates(base_entity: dict) -> None:
    EntityValidator().validate(base_entity)


def test_theme_rejects_missing_theme_kind(base_entity: dict) -> None:
    entity = {k: v for k, v in base_entity.items() if k != "theme_kind"}
    with pytest.raises(EntityValidationError, match="theme_kind"):
        EntityValidator().validate(entity)


def test_theme_kind_enum_enforced(base_entity: dict) -> None:
    entity = base_entity | {"theme_kind": "vibes"}
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_theme_scope_enum_enforced(base_entity: dict) -> None:
    entity = base_entity | {"theme_scope": "galactic"}
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)
