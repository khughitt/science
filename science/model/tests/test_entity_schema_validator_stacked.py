"""Tests for the validator with stacked bio extensions.

The composition pipeline (profile parsing + loader + allOf in
validator._compose) is already in place pre-Phase H. These tests
confirm it handles two- and three-segment stacks of bio extensions,
exposes the right errors, and caches schemas across repeated calls.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from science_model.entity_schema.loader import SchemaLoader, SchemaNotFoundError
from science_model.entity_schema.profile import ProfileComponent, parse_profile
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def stacked_rnaseq_matrix_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.matrix/1.0+bio.rnaseq/1.0",
        "id": "dataset:tcga-brca-rnaseq",
        "type": "dataset",
        "title": "TCGA-BRCA RNA-seq counts matrix",
        "version": "1.0.0",
        "created": "2026-05-19",
        "updated": "2026-05-19",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        # bio.matrix required:
        "n_rows": 20530,
        "n_cols": 1080,
        "value_dtype": "int32",
        "feature_axis": "rows",
        # bio.rnaseq required:
        "species": ["Homo sapiens"],
        "assay": "bulk-rnaseq",
    }


def test_profile_parses_four_segments() -> None:
    profile = parse_profile(
        "science-entity-base/1.0+dataset/1.0+bio.matrix/1.0+bio.rnaseq/1.0"
    )
    assert profile.base == ProfileComponent("science-entity-base", "1.0")
    assert profile.mixin == ProfileComponent("dataset", "1.0")
    assert profile.extensions == (
        ProfileComponent("bio.matrix", "1.0"),
        ProfileComponent("bio.rnaseq", "1.0"),
    )


def test_stacked_rnaseq_matrix_valid_entity_passes(
    stacked_rnaseq_matrix_entity: dict,
) -> None:
    EntityValidator().validate(stacked_rnaseq_matrix_entity)


def test_stacked_rnaseq_matrix_missing_bio_rnaseq_required_fails(
    stacked_rnaseq_matrix_entity: dict,
) -> None:
    """The composed allOf fails when one mixin's required field is absent."""
    fm = {k: v for k, v in stacked_rnaseq_matrix_entity.items() if k != "assay"}
    with pytest.raises(EntityValidationError, match="assay"):
        EntityValidator().validate(fm)


def test_stacked_rnaseq_matrix_missing_bio_matrix_required_fails(
    stacked_rnaseq_matrix_entity: dict,
) -> None:
    fm = {k: v for k, v in stacked_rnaseq_matrix_entity.items() if k != "value_dtype"}
    with pytest.raises(EntityValidationError, match="value_dtype"):
        EntityValidator().validate(fm)


def test_stacked_table_scrna_valid_entity_passes() -> None:
    fm = {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.table/1.0+bio.scrna/1.0",
        "id": "dataset:scrna-deg-table",
        "type": "dataset",
        "title": "scRNA-seq DEG table",
        "version": "1.0.0",
        "created": "2026-05-19",
        "updated": "2026-05-19",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        "n_records": 5000,
        "columns": [
            {"name": "gene_id", "dtype": "string", "kind": "feature-id"},
            {"name": "log2fc", "dtype": "float", "kind": "log2fc"},
        ],
        "species": ["Homo sapiens"],
        "assay": "10x-chromium-3prime",
    }
    EntityValidator().validate(fm)


def test_schema_loader_caches_extensions() -> None:
    """Loading the same extension twice hits the schema cache, not the disk."""
    loader = SchemaLoader()
    comp = ProfileComponent(name="bio.matrix", version="1.0")
    first = loader.load(comp)
    # Patch the resource read; second call must NOT trigger it.
    with patch(
        "science_model.entity_schema.loader._load_resource",
    ) as mock_read:
        second = loader.load(comp)
    assert mock_read.call_count == 0
    assert first is second


def test_unknown_extension_raises_schema_not_found(
    stacked_rnaseq_matrix_entity: dict,
) -> None:
    """An entity referencing an uninstalled extension fails loud."""
    stacked_rnaseq_matrix_entity["schema_profile"] = (
        "science-entity-base/1.0+dataset/1.0+bio.bogus/1.0"
    )
    with pytest.raises(SchemaNotFoundError, match="extension-bio-bogus-1.0.json"):
        EntityValidator().validate(stacked_rnaseq_matrix_entity)


def test_unknown_extension_in_middle_of_stack_also_raises() -> None:
    """Order doesn't matter — any unknown segment fails the composition."""
    fm = {
        "schema_profile": (
            "science-entity-base/1.0+dataset/1.0+bio.unknownmiddle/1.0+bio.rnaseq/1.0"
        ),
        "id": "dataset:x",
        "type": "dataset",
        "title": "x",
        "version": "1.0.0",
        "created": "2026-05-19",
        "updated": "2026-05-19",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        "species": ["Homo sapiens"],
        "assay": "bulk-rnaseq",
    }
    with pytest.raises(SchemaNotFoundError):
        EntityValidator().validate(fm)
