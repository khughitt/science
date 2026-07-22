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
    # Default estimand_type is interventional, which requires the pair.
    with pytest.raises(ValidationError, match="interventional estimand requires"):
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


def test_estimand_type_defaults_interventional():
    ent = PatchDefinitionEntity(
        **_base(profile="causal", status="specified", treatment="concept:drug", outcome="concept:recovery")
    )
    assert ent.inquiry.estimand_type == "interventional"


def test_causal_interventional_still_requires_treatment_outcome():
    with pytest.raises(ValidationError, match="interventional estimand requires"):
        PatchDefinitionEntity(**_base(profile="causal", status="specified", estimand_type="interventional"))


def test_causal_descriptive_estimand_omits_treatment_outcome():
    ent = PatchDefinitionEntity(**_base(profile="causal", status="specified", estimand_type="descriptive"))
    assert ent.inquiry.estimand_type == "descriptive"
    assert ent.inquiry.treatment is None
    assert ent.inquiry.outcome is None


def test_causal_associational_estimand_omits_treatment_outcome():
    ent = PatchDefinitionEntity(**_base(profile="causal", status="specified", estimand_type="associational"))
    assert ent.inquiry.estimand_type == "associational"


def test_causal_descriptive_may_still_carry_treatment_outcome():
    # A descriptive estimand MAY name variables (they just aren't an interventional
    # treatment/outcome pair); the exporter must not compute adjustment sets for it.
    ent = PatchDefinitionEntity(
        **_base(
            profile="causal",
            status="specified",
            estimand_type="descriptive",
            treatment="concept:frailty",
            outcome="concept:recovery",
        )
    )
    assert ent.inquiry.estimand_type == "descriptive"


def test_investigation_forbids_non_default_estimand_type():
    with pytest.raises(ValidationError, match="estimand_type is causal-only"):
        PatchDefinitionEntity(**_base(profile="investigation", status="sketch", estimand_type="descriptive"))


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
