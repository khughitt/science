from __future__ import annotations

import json
from pathlib import Path

import pytest

from science_model.entity_schema.validator import EntityValidationError, EntityValidator

_SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"


@pytest.fixture
def base_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0",
        "id": "dataset:cath-domains",
        "kind": "dataset",
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


def test_reference_dataset_does_not_require_datapackage(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "tier": "track",
        "dataset_class": "reference",
        "access": {
            "level": "public",
            "verified": True,
            "verification_method": "landing-confirmed",
            "source_url": "https://example.org/catalog",
        },
    }
    entity.pop("datapackage")

    EntityValidator().validate(entity)


def test_pointer_dataset_can_record_explicit_runtime_state_without_datapackage(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "tier": "track",
        "dataset_class": "pointer",
        "runtime_state": "pointer-only",
        "access": {
            "level": "public",
            "verified": True,
            "verification_method": "metadata-confirmed",
            "source_url": "https://example.org/record",
        },
    }
    entity.pop("datapackage")

    EntityValidator().validate(entity)


def test_deposit_dataset_still_requires_datapackage(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "dataset_class": "deposit",
        "access": {"level": "public", "verified": True},
    }
    entity.pop("datapackage")

    with pytest.raises(EntityValidationError, match="datapackage"):
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


def test_dataset_usage_schema_is_owned_by_base_schema() -> None:
    base_raw = (_SCHEMAS / "science-entity-base-1.0.json").read_text(encoding="utf-8")
    dataset_raw = (_SCHEMAS / "mixin-dataset-1.0.json").read_text(encoding="utf-8")
    base_schema = json.loads(base_raw)
    dataset_schema = json.loads(dataset_raw)

    assert "dataset_usage" in base_schema["properties"]
    assert "dataset_usage" not in dataset_schema["properties"]


def test_access_verification_method_vocabulary() -> None:
    dataset_raw = (_SCHEMAS / "mixin-dataset-1.0.json").read_text(encoding="utf-8")
    dataset_schema = json.loads(dataset_raw)

    enum = set(dataset_schema["$defs"]["access"]["properties"]["verification_method"]["enum"])

    assert enum == {
        "",
        "retrieved",
        "credential-confirmed",
        "landing-confirmed",
        "metadata-confirmed",
    }


def test_dataset_class_vocabulary() -> None:
    dataset_raw = (_SCHEMAS / "mixin-dataset-1.0.json").read_text(encoding="utf-8")
    dataset_schema = json.loads(dataset_raw)

    assert set(dataset_schema["properties"]["dataset_class"]["enum"]) == {"deposit", "reference", "pointer"}


def test_dataset_benchmark_block_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "benchmark": {
            "domains": ["biology"],
            "modalities": ["single-cell-rna-seq"],
            "signal_types": ["perturbation"],
            "benchmark_kinds": ["perturbation-response"],
            "source_datasets": ["GEO:GSE000"],
            "related_beliefs": ["hypothesis:h1"],
            "limitations": ["Small molecule perturbations only."],
            "tasks": [
                {
                    "id": "drug-response",
                    "task_type": "response-prediction",
                    "prediction_target": "post-treatment expression signature",
                    "held_out_unit": "compound",
                    "metric": "auroc",
                    "baseline": "mean-expression",
                    "ground_truth": {"type": "measured-outcome", "description": "expression state"},
                    "interpretation_limits": ["Landmark genes only."],
                    "intervention": "compound dose",
                    "timepoints": ["24h"],
                    "contexts": ["A549 cell line"],
                }
            ],
        },
    }

    EntityValidator().validate(entity)


def test_dataset_benchmark_supported_task_accepts_empty_reason(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "benchmark": {
            "tasks": [
                {
                    "id": "drug-response",
                    "support": {"state": "supported", "reason": "", "checked_at": ""},
                }
            ],
        },
    }

    EntityValidator().validate(entity)


def test_dataset_benchmark_task_accepts_null_support(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "benchmark": {
            "tasks": [
                {
                    "id": "drug-response",
                    "support": None,
                }
            ],
        },
    }

    EntityValidator().validate(entity)


@pytest.mark.parametrize(
    "support",
    [
        {"state": "blockd", "reason": "open-metadata-missing-progression-endpoint", "checked_at": "2026-07-02"},
        {"state": "blocked", "reason": "Missing Endpoint", "checked_at": "2026-07-02"},
        {"state": "blocked", "reason": "open-metadata-missing-progression-endpoint", "checked_at": "2026/07/02"},
    ],
)
def test_dataset_benchmark_task_rejects_invalid_support_fields(base_entity: dict, support: dict[str, str]) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "benchmark": {
            "tasks": [
                {
                    "id": "progression-risk",
                    "support": support,
                }
            ],
        },
    }

    with pytest.raises(EntityValidationError, match="benchmark"):
        EntityValidator().validate(entity)


@pytest.mark.parametrize(
    "support",
    [
        {"state": "supported", "evidence": ["recipe/reports/validation.json#x", ""]},
        {"state": "supported", "evidence": ["recipe/reports/validation.json#x", "   "]},
        {"state": "supported", "notes": ["Manual review.", ""]},
        {"state": "supported", "notes": ["Manual review.", "\t"]},
    ],
)
def test_dataset_benchmark_task_rejects_blank_support_list_items(base_entity: dict, support: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "benchmark": {
            "tasks": [
                {
                    "id": "progression-risk",
                    "support": support,
                }
            ],
        },
    }

    with pytest.raises(EntityValidationError, match="benchmark"):
        EntityValidator().validate(entity)


@pytest.mark.parametrize("task_id", ["Bad Task", "a-", "a--b"])
def test_dataset_benchmark_task_id_pattern_rejected(base_entity: dict, task_id: str) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "benchmark": {
            "benchmark_kinds": ["perturbation-response"],
            "tasks": [{"id": task_id, "task_type": "response-prediction"}],
        },
    }

    with pytest.raises(EntityValidationError, match="benchmark"):
        EntityValidator().validate(entity)


def test_dataset_benchmark_task_rejects_unknown_task_id_field(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "benchmark": {
            "benchmark_kinds": ["perturbation-response"],
            "tasks": [{"id": "drug-response", "task_id": "legacy-id", "task_type": "response-prediction"}],
        },
    }

    with pytest.raises(EntityValidationError, match="benchmark"):
        EntityValidator().validate(entity)


def test_dataset_benchmark_facet_type_rejected(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "benchmark": {"domains": "biology"},
    }

    with pytest.raises(EntityValidationError, match="benchmark"):
        EntityValidator().validate(entity)


# --- composition + aggregated-error coverage previously deferred from Task 4 ---


def test_validator_composes_base_plus_dataset_mixin() -> None:
    # End-to-end happy path: base + dataset/1.0 schemas now both exist, so a
    # real entity should validate. Confirms the validator's allOf composition
    # actually combines schemas correctly.
    entity = {
        "schema_profile": "science-entity-base/1.0+dataset/1.0",
        "id": "dataset:cath-domains",
        "kind": "dataset",
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


def test_dataset_observational_source_class_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "source_class": "observational",
    }
    EntityValidator().validate(entity)


def test_dataset_reference_source_class_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "source_class": "reference",
    }
    EntityValidator().validate(entity)


def test_dataset_source_class_invalid_enum_rejected(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "source_class": "curated",  # not in enum
    }
    with pytest.raises(EntityValidationError, match="source_class"):
        EntityValidator().validate(entity)


def test_dataset_derived_class_requires_derived_kind(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "source_class": "derived",  # derived_kind missing
    }
    with pytest.raises(EntityValidationError, match="derived_kind"):
        EntityValidator().validate(entity)


def test_dataset_derived_class_with_kind_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "source_class": "derived",
        "derived_kind": "model_output",
    }
    EntityValidator().validate(entity)


def test_dataset_derived_kind_without_derived_class_rejected(base_entity: dict) -> None:
    # derived_kind is only meaningful when source_class == derived.
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "source_class": "observational",
        "derived_kind": "aggregate",
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_dataset_usage_entry_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "source_class": "derived",
        "derived_kind": "model_output",
        "dataset_usage": [{"ref": "dataset:training-corpus", "role": "training", "overlap": "full"}],
    }
    EntityValidator().validate(entity)


def test_dataset_usage_bad_role_rejected(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "dataset_usage": [{"ref": "dataset:x", "role": "consulted"}],  # bad role
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_dataset_usage_ref_must_be_dataset_prefixed(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "dataset_usage": [{"ref": "paper:smith2024", "role": "analyzed"}],
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)
