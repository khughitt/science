from __future__ import annotations

import pytest

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_scrna_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.scrna/1.0",
        "id": "dataset:example-scrna",
        "type": "dataset",
        "title": "Example scRNA-seq dataset",
        "version": "1.0.0",
        "created": "2026-05-19",
        "updated": "2026-05-19",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        # bio.scrna required:
        "species": ["Homo sapiens"],
        "assay": "10x-chromium-3prime",
    }


def test_loader_resolves_bio_scrna_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.scrna", version="1.0"))
    assert schema["$id"].endswith("extension-bio-scrna-1.0.json")


def test_minimal_valid_scrna_passes(base_scrna_entity: dict) -> None:
    EntityValidator().validate(base_scrna_entity)


def test_species_as_array_passes(base_scrna_entity: dict) -> None:
    base_scrna_entity["species"] = ["Homo sapiens", "Mus musculus"]
    EntityValidator().validate(base_scrna_entity)


def test_species_as_string_fails(base_scrna_entity: dict) -> None:
    base_scrna_entity["species"] = "Homo sapiens"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_scrna_entity)


def test_species_empty_array_fails(base_scrna_entity: dict) -> None:
    base_scrna_entity["species"] = []
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_scrna_entity)


def test_assay_enum_accepts_known(base_scrna_entity: dict) -> None:
    for assay in ("smart-seq2", "drop-seq", "split-seq", "perturb-seq"):
        base_scrna_entity["assay"] = assay
        EntityValidator().validate(base_scrna_entity)


def test_assay_enum_rejects_unknown(base_scrna_entity: dict) -> None:
    base_scrna_entity["assay"] = "bulk-rnaseq"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_scrna_entity)


def test_missing_species_fails(base_scrna_entity: dict) -> None:
    fm = {k: v for k, v in base_scrna_entity.items() if k != "species"}
    with pytest.raises(EntityValidationError, match="species"):
        EntityValidator().validate(fm)


def test_missing_assay_fails(base_scrna_entity: dict) -> None:
    fm = {k: v for k, v in base_scrna_entity.items() if k != "assay"}
    with pytest.raises(EntityValidationError, match="assay"):
        EntityValidator().validate(fm)


def test_optional_tissue_passes(base_scrna_entity: dict) -> None:
    base_scrna_entity["tissue"] = "bone marrow"
    EntityValidator().validate(base_scrna_entity)
