from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent


@pytest.fixture
def base_schema() -> dict:
    loader = SchemaLoader()
    return loader.load(ProfileComponent(name="science-entity-base", version="1.0"))


def test_base_accepts_minimal_valid_entity(base_schema: dict) -> None:
    entity = {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "paper:Adams2025",
        "type": "paper",
        "title": "Example",
        "version": "1.0.0",
        "created": "2026-05-13",
        "updated": "2026-05-13",
    }
    Draft202012Validator(base_schema).validate(entity)


def test_base_rejects_missing_id(base_schema: dict) -> None:
    entity = {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "type": "paper",
        "title": "x",
        "version": "1.0.0",
        "created": "2026-05-13",
        "updated": "2026-05-13",
    }
    with pytest.raises(Exception):
        Draft202012Validator(base_schema).validate(entity)


def test_base_rejects_invalid_version_format(base_schema: dict) -> None:
    entity = {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "paper:Adams2025",
        "type": "paper",
        "title": "x",
        "version": "v1",  # invalid; must be semver
        "created": "2026-05-13",
        "updated": "2026-05-13",
    }
    with pytest.raises(Exception):
        Draft202012Validator(base_schema).validate(entity)


def test_base_rejects_invalid_type_value(base_schema: dict) -> None:
    entity = {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "x:y",
        "type": "unknown-type",
        "title": "x",
        "version": "1.0.0",
        "created": "2026-05-13",
        "updated": "2026-05-13",
    }
    with pytest.raises(Exception):
        Draft202012Validator(base_schema).validate(entity)


def test_base_accepts_optional_fields_when_present(base_schema: dict) -> None:
    entity = {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "paper:Adams2025",
        "type": "paper",
        "title": "x",
        "version": "1.0.0",
        "description": "A description",
        "created": "2026-05-13",
        "updated": "2026-05-13",
        "sources": ["doi:10.1234/abc", "cite:Adams2025"],
        "licenses": ["CC-BY-4.0"],
        "contributors": [{"name": "Ada", "role": "author"}],
        "ontology_terms": ["EFO:0000001"],
        "same_as": ["DOID:9538", "MeSH:D009101"],
        "tags": ["high-priority"],
    }
    Draft202012Validator(base_schema).validate(entity)


def test_base_rejects_invalid_date_format(base_schema: dict) -> None:
    # Validator must construct Draft202012Validator with FORMAT_CHECKER for
    # format: "date" to actually fire (jsonschema default ignores formats).
    entity = {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "paper:Adams2025",
        "type": "paper",
        "title": "x",
        "version": "1.0.0",
        "created": "not-a-date",
        "updated": "2026-05-13",
    }
    with pytest.raises(Exception, match="date"):
        Draft202012Validator(
            base_schema,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        ).validate(entity)


def test_loader_resolves_base_schema_now_that_it_exists() -> None:
    # This is the integration test we deferred from Task 3.
    schema = SchemaLoader().load(ProfileComponent(name="science-entity-base", version="1.0"))
    assert schema["$id"].endswith("science-entity-base-1.0.json")
    assert schema["type"] == "object"
