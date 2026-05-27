from __future__ import annotations

import pytest

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_registry_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.assembly_registry/1.0",
        "id": "dataset:assembly-registry",
        "type": "dataset",
        "title": "Assembly registry (seqcol-keyed reference collection)",
        "version": "1.0.0",
        "created": "2026-05-26",
        "updated": "2026-05-26",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        "member_key_column": "seqcol_digest",
        "assembly_count": 2,
    }


def test_loader_resolves_assembly_registry_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.assembly_registry", version="1.0"))
    assert schema["$id"].endswith("extension-bio-assembly_registry-1.0.json")


def test_minimal_valid_registry_passes(base_registry_entity: dict) -> None:
    EntityValidator().validate(base_registry_entity)


def test_member_key_column_required(base_registry_entity: dict) -> None:
    del base_registry_entity["member_key_column"]
    with pytest.raises(EntityValidationError, match="member_key_column"):
        EntityValidator().validate(base_registry_entity)


def test_member_key_column_must_be_seqcol_digest(base_registry_entity: dict) -> None:
    base_registry_entity["member_key_column"] = "accession"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_registry_entity)
