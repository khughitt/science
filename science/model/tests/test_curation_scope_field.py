"""CurationScope enum and the EntityKind.curation_scope field (shape only)."""

import pytest

from science_model.identity import CurationScope
from science_model.profiles.schema import EntityKind


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
