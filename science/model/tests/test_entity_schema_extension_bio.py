from __future__ import annotations

import pytest

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_rnaseq_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0",
        "id": "dataset:tcga-brca-rnaseq",
        "type": "dataset",
        "title": "TCGA-BRCA RNA-seq",
        "version": "1.0.0",
        "created": "2026-05-13",
        "updated": "2026-05-13",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        "species": ["Homo sapiens"],
        "assay": "bulk-rnaseq",
    }


def test_loader_resolves_extension_schema_now_that_it_exists() -> None:
    # Integration assertion for the loader's extension path (filename
    # mapping for dotted names → "extension-bio-rnaseq-1.0.json"). The
    # Task 3 loader test covered the mapping logic; this confirms the
    # real file is wired in.
    schema = SchemaLoader().load(ProfileComponent(name="bio.rnaseq", version="1.0"))
    assert schema["$id"].endswith("extension-bio-rnaseq-1.0.json")


def test_rnaseq_extension_composes_with_base_and_dataset(base_rnaseq_entity: dict) -> None:
    EntityValidator().validate(base_rnaseq_entity)


def test_rnaseq_rejects_missing_species(base_rnaseq_entity: dict) -> None:
    entity = {k: v for k, v in base_rnaseq_entity.items() if k != "species"}
    with pytest.raises(EntityValidationError, match="species"):
        EntityValidator().validate(entity)


def test_rnaseq_rejects_scalar_species(base_rnaseq_entity: dict) -> None:
    entity = base_rnaseq_entity | {"species": "Homo sapiens"}
    with pytest.raises(EntityValidationError, match="species"):
        EntityValidator().validate(entity)


def test_rnaseq_rejects_invalid_assay(base_rnaseq_entity: dict) -> None:
    entity = base_rnaseq_entity | {"assay": "RNA-seq"}  # uppercase rejected
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)
