from __future__ import annotations

import pytest

from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+topic/1.0",
        "id": "topic:single-cell-foundation-models",
        "kind": "topic",
        "title": "Single-cell foundation models",
        "version": "1.0.0",
        "status": "active",
        "created": "2026-05-13",
        "updated": "2026-05-13",
    }


def test_topic_minimal_validates(base_entity: dict) -> None:
    EntityValidator().validate(base_entity)


def test_topic_full_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "datasets": ["dataset:cellxgene"],
        "source_refs": ["cite:Cui2025"],
        "related": ["theme:cross-modal-representation"],
    }
    EntityValidator().validate(entity)


def test_topic_id_uppercase_rejected(base_entity: dict) -> None:
    entity = base_entity | {"id": "topic:Single-Cell"}
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)
