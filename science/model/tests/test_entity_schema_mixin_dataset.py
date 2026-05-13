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
