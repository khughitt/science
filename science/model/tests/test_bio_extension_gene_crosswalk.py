from __future__ import annotations

import pytest

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_crosswalk_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.gene_crosswalk/1.0",
        "id": "dataset:gene-crosswalk-hgnc",
        "kind": "dataset",
        "title": "HGNC gene crosswalk (gene_key-keyed reference collection)",
        "version": "1.0.0",
        "created": "2026-05-27",
        "updated": "2026-05-27",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        "member_key_column": "gene_key",
        "gene_count": 4,
    }


def test_loader_resolves_gene_crosswalk_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.gene_crosswalk", version="1.0"))
    assert schema["$id"].endswith("extension-bio-gene_crosswalk-1.0.json")


def test_minimal_valid_crosswalk_passes(base_crosswalk_entity: dict) -> None:
    EntityValidator().validate(base_crosswalk_entity)


def test_member_key_column_required(base_crosswalk_entity: dict) -> None:
    del base_crosswalk_entity["member_key_column"]
    with pytest.raises(EntityValidationError, match="member_key_column"):
        EntityValidator().validate(base_crosswalk_entity)


def test_member_key_column_must_be_gene_key(base_crosswalk_entity: dict) -> None:
    base_crosswalk_entity["member_key_column"] = "hgnc_id"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_crosswalk_entity)
