"""CurationScope enum and the EntityKind.curation_scope field (shape only)."""

import pytest

from science_model.identity import CurationScope
from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.schema import EntityKind

_EPISTEMIC = {
    "assumption",
    "chain-audit",
    "discussion",
    "evidence-line",
    "falsification",
    "finding",
    "hypothesis",
    "inquiry",
    "interpretation",
    "mechanism",
    "observation",
    "patch-definition",
    "proposition",
    "question",
    "report",
    "research-question",
    "story",
    "structural-chain",
    "synthesis",
    "theme",
    "validation-report",
}
_CORRESPONDENCE = {
    "claim-registry",
    "curation-sweep",
    "method",
    "plan",
    "pre-registration",
    "research-package",
    "spec",
    "transformation",
    "workflow",
}


def test_curation_scope_members():
    assert CurationScope.EPISTEMIC.value == "epistemic"
    assert CurationScope.CORRESPONDENCE.value == "correspondence"
    assert CurationScope.NONE.value == "none"


def test_entity_kind_curation_scope_defaults_none_field():
    ek = EntityKind(name="x", canonical_prefix="x", layer="layer/local", description="")
    assert ek.curation_scope is None  # undeclared, NOT resolved — resolution is the registry's job


def test_entity_kind_accepts_declared_scope():
    ek = EntityKind(
        name="plan",
        canonical_prefix="plan",
        layer="layer/core",
        description="",
        curation_scope=CurationScope.CORRESPONDENCE,
    )
    assert ek.curation_scope is CurationScope.CORRESPONDENCE


def test_entity_kind_coerces_string_scope():
    ek = EntityKind(
        name="hypothesis", canonical_prefix="hypothesis", layer="layer/core",
        description="", curation_scope="epistemic",
    )
    assert ek.curation_scope is CurationScope.EPISTEMIC


def test_entity_kind_rejects_unknown_scope():
    with pytest.raises(ValueError):
        EntityKind(name="x", canonical_prefix="x", layer="layer/local", description="", curation_scope="sometimes")


def test_core_profile_declares_epistemic_and_correspondence_only():
    declared = {
        ek.name: ek.curation_scope
        for ek in CORE_PROFILE.entity_kinds
        if ek.curation_scope is not None
    }
    assert {
        kind for kind, scope in declared.items() if scope is CurationScope.EPISTEMIC
    } == _EPISTEMIC
    assert {
        kind
        for kind, scope in declared.items()
        if scope is CurationScope.CORRESPONDENCE
    } == _CORRESPONDENCE
    # `none` kinds are left undeclared on purpose; the registry applies the default.
    assert all(scope is not CurationScope.NONE for scope in declared.values())
