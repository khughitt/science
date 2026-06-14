import pytest
from pydantic import ValidationError

from science_model.patch_definition import PatchDefinitionEntity


# Required base-Entity scaffolding fields (no defaults on science_model.entities.Entity).
_ENTITY_REQUIRED = {
    "project": "",
    "ontology_terms": [],
    "related": [],
    "source_refs": [],
    "content_preview": "",
    "file_path": "entities/patches/demo.md",
}


def _base(**inquiry):
    return {
        **_ENTITY_REQUIRED,
        "id": "patch-definition:p01-demo",
        "title": "Demo",
        "focal": "hypothesis:h01",
        "scope_set": [{"scope": "local"}],
        "neighborhood_policy": {},
        "patch_type": "inquiry",
        "inquiry": inquiry,
    }


def test_investigation_profile_minimal_valid():
    ent = PatchDefinitionEntity(**_base(profile="investigation", status="sketch"))
    assert ent.patch_type == "inquiry"
    assert ent.inquiry is not None
    assert ent.inquiry.profile == "investigation"


def test_causal_requires_treatment_and_outcome():
    with pytest.raises(ValidationError, match="causal profile requires"):
        PatchDefinitionEntity(**_base(profile="causal", status="specified"))


def test_causal_valid_with_estimand():
    ent = PatchDefinitionEntity(
        **_base(profile="causal", status="specified", treatment="concept:drug", outcome="concept:recovery")
    )
    assert ent.inquiry.treatment == "concept:drug"
    assert ent.inquiry.outcome == "concept:recovery"


def test_investigation_forbids_estimand():
    with pytest.raises(ValidationError, match="investigation profile must not"):
        PatchDefinitionEntity(**_base(profile="investigation", status="sketch", treatment="concept:drug"))


def test_inquiry_block_required_when_patch_type_inquiry():
    data = {
        **_ENTITY_REQUIRED,
        "id": "patch-definition:p02-x",
        "title": "X",
        "focal": "hypothesis:h01",
        "scope_set": [{"scope": "local"}],
        "neighborhood_policy": {},
        "patch_type": "inquiry",
    }
    with pytest.raises(ValidationError, match="requires an inquiry block"):
        PatchDefinitionEntity(**data)


def test_inquiry_block_forbidden_for_plain_patch():
    data = {
        **_ENTITY_REQUIRED,
        "id": "patch-definition:p03-x",
        "title": "X",
        "focal": "hypothesis:h01",
        "scope_set": [{"scope": "local"}],
        "neighborhood_policy": {},
        "inquiry": {"profile": "investigation", "status": "sketch"},
    }
    with pytest.raises(ValidationError, match="only allowed when patch_type"):
        PatchDefinitionEntity(**data)


def test_boundary_role_enum_enforced():
    with pytest.raises(ValidationError):
        PatchDefinitionEntity(
            **_base(profile="investigation", status="sketch", boundary_roles=[{"ref": "concept:x", "role": "Bogus"}])
        )
