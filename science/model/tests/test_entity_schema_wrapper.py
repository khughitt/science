from __future__ import annotations

import pytest

from science_model.entity_schema.wrapper import SharedEntity


def test_wrapper_loads_paper_entity() -> None:
    raw = {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "paper:Adams2025",
        "type": "paper",
        "title": "An example",
        "version": "1.0.0",
        "created": "2026-05-13",
        "updated": "2026-05-13",
        "bibkey": "Adams2025",
        "year": 2025,
        "datasets": ["dataset:cath-domains"],
    }
    entity = SharedEntity.model_validate(raw)
    assert entity.id == "paper:Adams2025"
    assert entity.type == "paper"
    assert entity.version == "1.0.0"
    assert entity.extra.get("bibkey") == "Adams2025"
    assert entity.extra.get("datasets") == ["dataset:cath-domains"]


def test_wrapper_validates_with_validator() -> None:
    # The wrapper does NOT replace the JSON Schema validator; it's a convenience layer.
    raw = {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "paper:Adams2025",
        "type": "paper",
        "title": "An example",
        "version": "1.0.0",
        "created": "2026-05-13",
        "updated": "2026-05-13",
    }
    entity = SharedEntity.model_validate(raw)
    entity.validate_schema()  # delegates to EntityValidator under the hood


def test_wrapper_raises_on_schema_violation() -> None:
    raw = {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "paper:Adams2025",
        "type": "paper",
        "title": "An example",
        "version": "1.0.0",
        # missing required: created, updated
    }
    entity = SharedEntity.model_validate(raw)
    with pytest.raises(Exception, match="created"):
        entity.validate_schema()
