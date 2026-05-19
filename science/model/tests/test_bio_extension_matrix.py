from __future__ import annotations

import pytest

from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_matrix_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.matrix/1.0",
        "id": "dataset:example-matrix",
        "type": "dataset",
        "title": "Example matrix dataset",
        "version": "1.0.0",
        "created": "2026-05-19",
        "updated": "2026-05-19",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        # bio.matrix required fields:
        "n_rows": 20000,
        "n_cols": 500,
        "value_dtype": "int32",
        "feature_axis": "rows",
    }


def test_loader_resolves_bio_matrix_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.matrix", version="1.0"))
    assert schema["$id"].endswith("extension-bio-matrix-1.0.json")


def test_minimal_valid_matrix_passes(base_matrix_entity: dict) -> None:
    EntityValidator().validate(base_matrix_entity)


def test_missing_n_rows_fails(base_matrix_entity: dict) -> None:
    fm = {k: v for k, v in base_matrix_entity.items() if k != "n_rows"}
    with pytest.raises(EntityValidationError, match="n_rows"):
        EntityValidator().validate(fm)


def test_missing_n_cols_fails(base_matrix_entity: dict) -> None:
    fm = {k: v for k, v in base_matrix_entity.items() if k != "n_cols"}
    with pytest.raises(EntityValidationError, match="n_cols"):
        EntityValidator().validate(fm)


def test_missing_value_dtype_fails(base_matrix_entity: dict) -> None:
    fm = {k: v for k, v in base_matrix_entity.items() if k != "value_dtype"}
    with pytest.raises(EntityValidationError, match="value_dtype"):
        EntityValidator().validate(fm)


def test_missing_feature_axis_fails(base_matrix_entity: dict) -> None:
    fm = {k: v for k, v in base_matrix_entity.items() if k != "feature_axis"}
    with pytest.raises(EntityValidationError, match="feature_axis"):
        EntityValidator().validate(fm)


def test_value_dtype_enum_rejects_invalid(base_matrix_entity: dict) -> None:
    base_matrix_entity["value_dtype"] = "complex128"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_matrix_entity)


def test_feature_axis_enum_rejects_invalid(base_matrix_entity: dict) -> None:
    base_matrix_entity["feature_axis"] = "diagonal"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_matrix_entity)


def test_n_rows_must_be_positive_int(base_matrix_entity: dict) -> None:
    base_matrix_entity["n_rows"] = 0
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_matrix_entity)


def test_optional_row_col_kind_pass(base_matrix_entity: dict) -> None:
    base_matrix_entity["row_kind"] = "gene"
    base_matrix_entity["col_kind"] = "sample"
    EntityValidator().validate(base_matrix_entity)
