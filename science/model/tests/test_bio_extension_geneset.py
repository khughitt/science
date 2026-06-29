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


def test_loader_resolves_geneset_member_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.geneset.member", version="1.0"))
    assert schema["$id"].endswith("extension-bio-geneset-member-1.0.json")


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


def test_minimal_valid_geneset_member_passes() -> None:
    EntityValidator().validate(
        {
            "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.geneset.member/1.0",
            "id": "dataset:reactome-r-hsa-1",
            "type": "dataset",
            "title": "R-HSA-1",
            "version": "1.0.0",
            "created": "2026-05-28",
            "updated": "2026-05-28",
            "datapackage": "virtual:member-of",
            "origin": "derived",
            "tier": "use-now",
            "source_class": "reference",
            "parent_dataset": "dataset:reactome-v89",
            "derivation": {
                "kind": "member_of",
                "parent_dataset": "dataset:reactome-v89",
                "member_key": "R-HSA-1",
            },
            "identifier_space": {
                "tier": "gene",
                "namespace": "hgnc_id",
                "registry": "dataset:gene-crosswalk-hgnc",
                "resolution_status": "resolved",
            },
            "n_members": 2,
        }
    )


@pytest.mark.parametrize("field", ["identifier_space", "n_members"])
def test_geneset_member_requires_extension_fields(field: str) -> None:
    entity = {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.geneset.member/1.0",
        "id": "dataset:reactome-r-hsa-1",
        "type": "dataset",
        "title": "R-HSA-1",
        "version": "1.0.0",
        "created": "2026-05-28",
        "updated": "2026-05-28",
        "datapackage": "virtual:member-of",
        "origin": "derived",
        "tier": "use-now",
        "source_class": "reference",
        "parent_dataset": "dataset:reactome-v89",
        "derivation": {
            "kind": "member_of",
            "parent_dataset": "dataset:reactome-v89",
            "member_key": "R-HSA-1",
        },
        "identifier_space": {"tier": "gene", "namespace": "hgnc_id"},
        "n_members": 2,
    }
    del entity[field]

    with pytest.raises(EntityValidationError, match=field):
        EntityValidator().validate(entity)


def test_geneset_member_rejects_scalar_member_key_duplicate() -> None:
    with pytest.raises(EntityValidationError, match="member_key"):
        EntityValidator().validate(
            {
                "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.geneset.member/1.0",
                "id": "dataset:reactome-r-hsa-1",
                "type": "dataset",
                "title": "R-HSA-1",
                "version": "1.0.0",
                "created": "2026-05-28",
                "updated": "2026-05-28",
                "datapackage": "virtual:member-of",
                "origin": "derived",
                "tier": "use-now",
                "source_class": "reference",
                "parent_dataset": "dataset:reactome-v89",
                "derivation": {
                    "kind": "member_of",
                    "parent_dataset": "dataset:reactome-v89",
                    "member_key": "R-HSA-1",
                },
                "identifier_space": {"tier": "gene", "namespace": "hgnc_id"},
                "n_members": 2,
                "member_key": "R-HSA-1",
            }
        )
