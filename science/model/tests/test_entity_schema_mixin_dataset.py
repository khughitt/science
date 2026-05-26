from __future__ import annotations

import pytest

from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0",
        "id": "dataset:cath-domains",
        "type": "dataset",
        "title": "CATH domain database",
        "version": "1.0.0",
        "created": "2026-05-13",
        "updated": "2026-05-13",
        "datapackage": "datapackage.yaml",
        "tier": "use-now",
    }


def test_dataset_external_with_access_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "accessions": ["CATH:v4_3_0"],
    }
    EntityValidator().validate(entity)


def test_dataset_derived_with_derivation_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "derived",
        "derivation": {
            "workflow_recipe": "recipe/Snakefile",
            "recipe_lockfile": "recipe/lockfile.yaml",
            "inputs": ["dataset:upstream"],
        },
    }
    EntityValidator().validate(entity)


def test_dataset_external_missing_access_rejected(base_entity: dict) -> None:
    entity = base_entity | {"origin": "external"}
    with pytest.raises(EntityValidationError, match="access"):
        EntityValidator().validate(entity)


def test_dataset_with_resources_field_rejected(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "resources": [{"name": "x", "path": "x.parquet"}],
    }
    with pytest.raises(EntityValidationError, match="resources"):
        EntityValidator().validate(entity)


def test_dataset_id_must_start_with_dataset_prefix(base_entity: dict) -> None:
    entity = base_entity | {
        "id": "paper:wrong",
        "origin": "external",
        "access": {"level": "public", "verified": True},
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_dataset_id_slug_lowercase_kebab_only(base_entity: dict) -> None:
    entity = base_entity | {
        "id": "dataset:NotKebab",  # uppercase rejected for datasets
        "origin": "external",
        "access": {"level": "public", "verified": True},
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


# --- composition + aggregated-error coverage previously deferred from Task 4 ---


def test_validator_composes_base_plus_dataset_mixin() -> None:
    # End-to-end happy path: base + dataset/1.0 schemas now both exist, so a
    # real entity should validate. Confirms the validator's allOf composition
    # actually combines schemas correctly.
    entity = {
        "schema_profile": "science-entity-base/1.0+dataset/1.0",
        "id": "dataset:cath-domains",
        "type": "dataset",
        "title": "CATH domain database",
        "version": "1.0.0",
        "created": "2026-05-13",
        "updated": "2026-05-13",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
    }
    EntityValidator().validate(entity)


def test_validator_aggregates_errors_across_base_and_mixin() -> None:
    bad = {
        "schema_profile": "science-entity-base/1.0+dataset/1.0",
        # missing base-required (id, type, title, version, created, updated)
        # AND mixin-required (datapackage, origin, tier).
    }
    with pytest.raises(EntityValidationError) as info:
        EntityValidator().validate(bad)
    message = str(info.value)
    # At least one base error and one mixin error present in the joined message.
    assert "title" in message
    assert "datapackage" in message


def test_dataset_member_of_derivation_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "derived",
        "parent_dataset": "dataset:reactome-v89",
        "derivation": {
            "kind": "member_of",
            "parent_dataset": "dataset:reactome-v89",
            "member_key": "R-HSA-12345",
        },
    }
    EntityValidator().validate(entity)


def test_dataset_workflow_derivation_without_kind_still_validates(base_entity: dict) -> None:
    # Backward-compatibility: existing derived datasets carry no `kind`.
    entity = base_entity | {
        "origin": "derived",
        "derivation": {
            "workflow_recipe": "recipe/Snakefile",
            "recipe_lockfile": "recipe/lockfile.yaml",
            "inputs": ["dataset:upstream"],
        },
    }
    EntityValidator().validate(entity)


def test_dataset_member_of_missing_member_key_rejected(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "derived",
        "derivation": {"kind": "member_of", "parent_dataset": "dataset:reactome-v89"},
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_dataset_member_of_with_workflow_fields_rejected(base_entity: dict) -> None:
    # member_of must not also carry workflow fields (RCM-D5: a member has no workflow).
    entity = base_entity | {
        "origin": "derived",
        "derivation": {
            "kind": "member_of",
            "parent_dataset": "dataset:reactome-v89",
            "member_key": "R-HSA-12345",
            "workflow_recipe": "recipe/Snakefile",
            "inputs": ["dataset:upstream"],
        },
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_dataset_member_of_with_recipe_lockfile_rejected(base_entity: dict) -> None:
    # recipe_lockfile is a workflow field; a member_of has no workflow (RCM-D5).
    entity = base_entity | {
        "origin": "derived",
        "derivation": {
            "kind": "member_of",
            "parent_dataset": "dataset:reactome-v89",
            "member_key": "R-HSA-12345",
            "recipe_lockfile": "recipe/lockfile.yaml",
        },
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_dataset_explicit_workflow_kind_validates(base_entity: dict) -> None:
    # Branch 1 accepts an explicit kind: "workflow" (guards the const).
    entity = base_entity | {
        "origin": "derived",
        "derivation": {
            "kind": "workflow",
            "workflow_recipe": "recipe/Snakefile",
            "inputs": ["dataset:upstream"],
        },
    }
    EntityValidator().validate(entity)


def test_dataset_member_of_without_top_level_parent_dataset_validates(base_entity: dict) -> None:
    # The schema does not couple top-level parent_dataset to derivation.parent_dataset;
    # a member_of with only the derivation-level parent_dataset is valid.
    entity = base_entity | {
        "origin": "derived",
        "derivation": {
            "kind": "member_of",
            "parent_dataset": "dataset:reactome-v89",
            "member_key": "R-HSA-12345",
        },
    }
    EntityValidator().validate(entity)


def test_dataset_top_level_parent_dataset_pattern_enforced(base_entity: dict) -> None:
    # Top-level parent_dataset must carry the dataset: prefix.
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "parent_dataset": "reactome-v89",  # missing dataset: prefix
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)
