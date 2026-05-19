from __future__ import annotations

import pytest

from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_table_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.table/1.0",
        "id": "dataset:example-table",
        "type": "dataset",
        "title": "Example table dataset",
        "version": "1.0.0",
        "created": "2026-05-19",
        "updated": "2026-05-19",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        # bio.table required fields:
        "n_records": 18000,
        "columns": [
            {"name": "gene_id", "dtype": "string", "kind": "feature-id"},
            {"name": "log2fc", "dtype": "float", "kind": "log2fc"},
            {"name": "padj", "dtype": "float", "kind": "padj"},
        ],
    }


def test_loader_resolves_bio_table_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.table", version="1.0"))
    assert schema["$id"].endswith("extension-bio-table-1.0.json")


def test_minimal_valid_table_passes(base_table_entity: dict) -> None:
    EntityValidator().validate(base_table_entity)


def test_missing_n_records_fails(base_table_entity: dict) -> None:
    fm = {k: v for k, v in base_table_entity.items() if k != "n_records"}
    with pytest.raises(EntityValidationError, match="n_records"):
        EntityValidator().validate(fm)


def test_n_records_must_be_positive_int(base_table_entity: dict) -> None:
    base_table_entity["n_records"] = 0
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_table_entity)


def test_missing_columns_fails(base_table_entity: dict) -> None:
    fm = {k: v for k, v in base_table_entity.items() if k != "columns"}
    with pytest.raises(EntityValidationError, match="columns"):
        EntityValidator().validate(fm)


def test_empty_columns_fails(base_table_entity: dict) -> None:
    base_table_entity["columns"] = []
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_table_entity)


def test_column_missing_kind_fails(base_table_entity: dict) -> None:
    base_table_entity["columns"][0].pop("kind")
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_table_entity)


def test_column_unknown_key_fails(base_table_entity: dict) -> None:
    """Inner column descriptor uses additionalProperties: false."""
    base_table_entity["columns"][0]["bogus"] = "x"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_table_entity)


def test_column_dtype_enum_rejects_invalid(base_table_entity: dict) -> None:
    base_table_entity["columns"][0]["dtype"] = "complex128"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_table_entity)
