from __future__ import annotations

import pytest

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_crosswalk_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.protein_crosswalk/1.0",
        "id": "dataset:protein-crosswalk-uniprot",
        "type": "dataset",
        "title": "UniProt protein crosswalk (protein_key-keyed reference collection)",
        "version": "1.0.0",
        "created": "2026-05-27",
        "updated": "2026-05-27",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        "member_key_column": "protein_key",
        "protein_count": 4,
    }


def test_loader_resolves_protein_crosswalk_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.protein_crosswalk", version="1.0"))
    assert schema["$id"].endswith("extension-bio-protein_crosswalk-1.0.json")


def test_minimal_valid_crosswalk_passes(base_crosswalk_entity: dict) -> None:
    EntityValidator().validate(base_crosswalk_entity)


def test_member_key_column_required(base_crosswalk_entity: dict) -> None:
    del base_crosswalk_entity["member_key_column"]
    with pytest.raises(EntityValidationError, match="member_key_column"):
        EntityValidator().validate(base_crosswalk_entity)


def test_member_key_column_must_be_protein_key(base_crosswalk_entity: dict) -> None:
    base_crosswalk_entity["member_key_column"] = "uniprot_accession"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_crosswalk_entity)
