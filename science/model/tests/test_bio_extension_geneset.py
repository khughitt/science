from __future__ import annotations

import pytest

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_geneset_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.geneset/1.0",
        "id": "dataset:reactome-v89",
        "type": "dataset",
        "title": "Reactome v89 gene-set collection",
        "version": "1.0.0",
        "created": "2026-05-28",
        "updated": "2026-05-28",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "source_class": "reference",
        "access": {"level": "public", "verified": True},
        "member_key_column": "set_key",
        "members_resource": "sets",
        "n_sets": 2,
        "set_size_summary": {"min": 3, "median": 4, "max": 5},
        "identifier_space": {
            "tier": "gene",
            "namespace": "hgnc_id",
            "registry": "dataset:gene-crosswalk-hgnc",
            "resolution_status": "resolved",
        },
    }


def test_loader_resolves_geneset_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.geneset", version="1.0"))
    assert schema["$id"].endswith("extension-bio-geneset-1.0.json")


def test_minimal_valid_geneset_collection_passes(base_geneset_entity: dict) -> None:
    EntityValidator().validate(base_geneset_entity)


def test_member_key_column_must_be_set_key(base_geneset_entity: dict) -> None:
    base_geneset_entity["member_key_column"] = "pathway_id"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_geneset_entity)


def test_identifier_space_requires_supported_tier_shape(base_geneset_entity: dict) -> None:
    del base_geneset_entity["identifier_space"]["namespace"]
    with pytest.raises(EntityValidationError, match="namespace"):
        EntityValidator().validate(base_geneset_entity)
