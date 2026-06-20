from __future__ import annotations

import pytest

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_cna_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.cna/1.0",
        "id": "dataset:example-cna",
        "type": "dataset",
        "title": "Example CNA dataset",
        "version": "1.0.0",
        "created": "2026-05-19",
        "updated": "2026-05-19",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        # bio.cna required:
        "species": ["Homo sapiens"],
        "assay": "snp-array",
    }


def test_loader_resolves_bio_cna_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.cna", version="1.0"))
    assert schema["$id"].endswith("extension-bio-cna-1.0.json")


def test_minimal_valid_cna_passes(base_cna_entity: dict) -> None:
    EntityValidator().validate(base_cna_entity)


def test_assay_enum_accepts_known(base_cna_entity: dict) -> None:
    for assay in ("snp-array", "array-cgh", "wes-cna", "wgs-cna", "shallow-wgs"):
        base_cna_entity["assay"] = assay
        EntityValidator().validate(base_cna_entity)


def test_assay_enum_rejects_unknown(base_cna_entity: dict) -> None:
    base_cna_entity["assay"] = "bulk-rnaseq"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_cna_entity)


def test_species_as_string_fails(base_cna_entity: dict) -> None:
    base_cna_entity["species"] = "Homo sapiens"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_cna_entity)


def test_missing_species_fails(base_cna_entity: dict) -> None:
    fm = {k: v for k, v in base_cna_entity.items() if k != "species"}
    with pytest.raises(EntityValidationError, match="species"):
        EntityValidator().validate(fm)


def test_missing_assay_fails(base_cna_entity: dict) -> None:
    fm = {k: v for k, v in base_cna_entity.items() if k != "assay"}
    with pytest.raises(EntityValidationError, match="assay"):
        EntityValidator().validate(fm)


def test_optional_segmentation_method_passes(base_cna_entity: dict) -> None:
    base_cna_entity["segmentation_method"] = "CBS"
    EntityValidator().validate(base_cna_entity)
