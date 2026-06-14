from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.patch_definition import (
    LocalClosurePolicy,
    PatchDefinitionEntity,
    PatchExclude,
    PatchScope,
)


def _base_patch(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "patch-definition:apoptosis-mcl1",
        "canonical_id": "patch-definition:apoptosis-mcl1",
        "kind": "patch-definition",
        "type": "patch-definition",
        "title": "Apoptosis MCL1 patch",
        "status": "active",
        "project": "",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": "entities/patches/apoptosis-mcl1.md",
        "focal": "hypothesis:h01-apoptosis",
        "scope_set": [{"scope": "local"}],
        "neighborhood_policy": {
            "name": "local-closure-v1",
            "version": "local-closure-v1",
            "max_depth": 2,
        },
    }
    data.update(overrides)
    return data


def test_patch_definition_valid_minimal() -> None:
    entity = PatchDefinitionEntity.model_validate(_base_patch())

    assert entity.kind == "patch-definition"
    assert entity.focal == "hypothesis:h01-apoptosis"
    assert entity.scope_set == [PatchScope(scope="local")]
    assert entity.neighborhood_policy == LocalClosurePolicy()
    assert entity.seeds == []
    assert entity.excludes == []


def test_patch_definition_requires_focal() -> None:
    data = _base_patch()
    data.pop("focal")

    with pytest.raises(ValidationError, match="focal"):
        PatchDefinitionEntity.model_validate(data)


def test_patch_definition_rejects_non_local_scope() -> None:
    with pytest.raises(ValidationError, match="remote scopes deferred"):
        PatchDefinitionEntity.model_validate(
            _base_patch(scope_set=[{"scope": "commons", "ref": "commons"}])
        )


def test_patch_definition_rejects_empty_scope_set() -> None:
    with pytest.raises(ValidationError, match="scope_set"):
        PatchDefinitionEntity.model_validate(_base_patch(scope_set=[]))


def test_patch_definition_exclude_reason_required_and_nonempty() -> None:
    with pytest.raises(ValidationError, match="reason"):
        PatchDefinitionEntity.model_validate(
            _base_patch(excludes=[{"ref": "proposition:p1"}])
        )

    with pytest.raises(ValidationError, match="reason must be non-empty"):
        PatchExclude.model_validate({"ref": "proposition:p1", "reason": "  "})


def test_patch_definition_rejects_unknown_policy() -> None:
    with pytest.raises(ValidationError, match="Input should be 'local-closure-v1'"):
        PatchDefinitionEntity.model_validate(
            _base_patch(neighborhood_policy={"name": "latent-v1", "version": "latent-v1"})
        )


def test_patch_definition_rejects_invalid_max_depth() -> None:
    with pytest.raises(ValidationError, match="max_depth"):
        PatchDefinitionEntity.model_validate(
            _base_patch(
                neighborhood_policy={
                    "name": "local-closure-v1",
                    "version": "local-closure-v1",
                    "max_depth": 0,
                }
            )
        )
