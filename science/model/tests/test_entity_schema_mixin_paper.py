from __future__ import annotations

import pytest

from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "paper:Adams2025",
        "type": "paper",
        "title": "An interesting paper",
        "version": "1.0.0",
        "status": "active",
        "created": "2026-05-13",
        "updated": "2026-05-13",
    }


def test_paper_minimal_validates(base_entity: dict) -> None:
    EntityValidator().validate(base_entity)


def test_paper_with_rich_fields_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "bibkey": "Adams2025",
        "authors": ["Adams, A.", "Baker, B."],
        "year": 2025,
        "journal": "Nature Methods",
        "doi": "10.1038/x.y.z",
        "url": "https://example.org/Adams2025",
        "datasets": ["dataset:cath-domains"],
        "key_findings": ["finding 1", "finding 2"],
        "methods_summary": "They used method X.",
        "limitations": ["small sample"],
        "model_or_tool_availability": "available at https://...",
    }
    EntityValidator().validate(entity)


def test_paper_id_lowercase_slug_rejected(base_entity: dict) -> None:
    entity = base_entity | {"id": "paper:adams-2025"}  # kebab rejected for papers
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_paper_id_bibkey_accepted(base_entity: dict) -> None:
    entity = base_entity | {"id": "paper:BarrioHernandez2023"}
    EntityValidator().validate(entity)


def test_paper_year_rejects_non_integer(base_entity: dict) -> None:
    entity = base_entity | {"year": "2025"}
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_paper_datasets_must_be_dataset_refs(base_entity: dict) -> None:
    entity = base_entity | {"datasets": ["paper:OtherThing"]}
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)
