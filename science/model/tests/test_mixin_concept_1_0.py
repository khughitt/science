"""Probes for the DORMANT `mixin-concept-1.0` schema.

Step 2 of the concept slice. The mixin exists on disk but no generation row selects
it and `schema_closed` is still False, so nothing here changes what the toolkit
loads today. These probes fix the candidate contract before the production surfaces
are aligned to it.

Every strict probe composes the candidate profile through the REAL
`EntityValidator._compose` (via `validate_as`). Hand-rolling
`{"allOf": [...], "unevaluatedProperties": False}` here instead would certify this
test file's idea of composition rather than the toolkit's.

Arming a kind flips TWO independent lookups, and the fixture patches both because
step 7 will satisfy both from one declaration:

- `validator.py:135` gates `unevaluatedProperties: false` on `PROJECT_MIXIN_NAMES`;
- `loader.py:92` gates the `mixin-` filename prefix on `TYPE_MIXIN_NAMES`, so an
  unarmed name resolves to `extension-concept-1.0.json` and is not found at all.

Both are patched in the CONSUMING module's namespace, not in `profile`: each does
`from ...profile import <NAME>`, which binds a new name at import time, so rebinding
the source module would not be seen.
"""

import json
from pathlib import Path

import pytest
from science_model.entity_schema import loader as loader_module
from science_model.entity_schema import validator as validator_module
from science_model.entity_schema.loader import SchemaNotFoundError
from science_model.entity_schema.profile import (
    BASE_NAME,
    PROJECT_MIXIN_NAMES,
    TYPE_MIXIN_NAMES,
    ProfileComponent,
    ProfileParseError,
    ProfileString,
    default_profile_for_kind,
)
from science_model.entity_schema.validator import EntityValidationError, EntityValidator

SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"

CANDIDATE = ProfileString(
    base=ProfileComponent(BASE_NAME, "2.0"),
    mixin=ProfileComponent("concept", "1.0"),
    extensions=(),
)

# The frozen literal oracle for `promoted_from`, transcribed from
# ~/d/protein-landscape/schemas/extension-protein-landscape-promotion-1.0.json.
# Hand-authored here on purpose: comparing this mixin against another MIXIN would let
# every admitting mixin drift to the same wrong value together, which is the tautology
# defect one level down.
PROMOTED_FROM_ORACLE = {
    "type": "string",
    "minLength": 1,
    "description": (
        "Path of the source file this entity was promoted from, "
        "e.g. knowledge/sources/local/entities.yaml"
    ),
}


def _mixin() -> dict:
    return json.loads((SCHEMAS / "mixin-concept-1.0.json").read_text())


def _record(**overrides) -> dict:
    """A minimal record every one of the 329 authored concepts satisfies."""
    record = {
        "id": "concept:age",
        "kind": "concept",
        "title": "Age",
        "status": "active",
        "created": "2026-06-10",
        "updated": "2026-06-10",
    }
    record.update(overrides)
    return record


@pytest.fixture
def strict(monkeypatch) -> EntityValidator:
    """An EntityValidator that composes `concept` STRICTLY, as step 7 eventually will."""
    monkeypatch.setattr(
        validator_module, "PROJECT_MIXIN_NAMES", PROJECT_MIXIN_NAMES | {"concept"}
    )
    monkeypatch.setattr(loader_module, "TYPE_MIXIN_NAMES", TYPE_MIXIN_NAMES | {"concept"})
    return EntityValidator()


def _refuses(validator: EntityValidator, record: dict) -> str:
    with pytest.raises(EntityValidationError) as caught:
        validator.validate_as(record, CANDIDATE)
    return str(caught.value)


# --- dormancy: this branch arms nothing ------------------------------------------


def test_concept_is_not_yet_armed():
    assert "concept" not in PROJECT_MIXIN_NAMES


@pytest.mark.parametrize("generation", [2, 3])
def test_no_generation_row_selects_the_concept_mixin(generation):
    with pytest.raises(ProfileParseError):
        default_profile_for_kind("concept", generation=generation)


def test_the_mixin_is_unreachable_while_unarmed():
    """Dormancy is stronger than "not strict": the file cannot be loaded as a mixin.

    `loader.py:92` derives the filename prefix from `TYPE_MIXIN_NAMES`, so an unarmed
    `concept` resolves to `extension-concept-1.0.json`, which does not exist. Adding
    this file to the package therefore cannot change any current load path -- and this
    assertion is one of the two that must flip at step 7.
    """
    with pytest.raises(SchemaNotFoundError) as caught:
        EntityValidator().validate_as(_record(), CANDIDATE)
    assert "extension-concept-1.0.json" in str(caught.value)


def test_unarmed_composition_would_not_close(monkeypatch):
    """The other half of dormancy: reachable but lax.

    With ONLY the loader patched, `_compose` still omits `unevaluatedProperties`,
    so a key no surface declares sails through. That is the defect the slice closes,
    asserted against the real composer rather than described.
    """
    monkeypatch.setattr(loader_module, "TYPE_MIXIN_NAMES", TYPE_MIXIN_NAMES | {"concept"})
    EntityValidator().validate_as(_record(shadow_key="unvouched"), CANDIDATE)


# --- value probes: the measured corpus validates ---------------------------------


def test_minimal_authored_record_validates(strict):
    strict.validate_as(_record(), CANDIDATE)


def test_record_with_every_observed_non_base_field_validates(strict):
    strict.validate_as(
        _record(
            profile="local",
            promoted_from="knowledge/sources/local/terms.yaml",
            related=["concept:immune-evasion"],
            source_refs=["paper:smith2021"],
        ),
        CANDIDATE,
    )


def test_health_variant_with_empty_ontology_terms_validates(strict):
    """All 37 `~/d/health` concepts carry `ontology_terms`, and all 37 carry it empty."""
    strict.validate_as(_record(ontology_terms=[]), CANDIDATE)


@pytest.mark.parametrize(
    "value",
    [
        "knowledge/sources/local/terms.yaml",
        "knowledge/sources/local/entities.yaml",
        "knowledge/sources/project_specific/entities.yaml",
    ],
)
def test_every_promoted_from_value_in_the_corpus_validates(strict, value):
    """The three distinct values across the 132 concepts that carry the field."""
    strict.validate_as(_record(promoted_from=value), CANDIDATE)


@pytest.mark.parametrize("value", ["local", "project_specific"])
def test_every_profile_value_in_the_corpus_validates(strict, value):
    """`core` -- ProjectEntity's default -- is deliberately absent: no record carries it."""
    strict.validate_as(_record(profile=value), CANDIDATE)


# --- mutation probes: what the closed schema must refuse -------------------------


def test_undeclared_key_is_refused(strict):
    assert "shadow_key" in _refuses(strict, _record(shadow_key="unvouched"))


def test_foreign_kind_is_refused(strict):
    _refuses(strict, _record(kind="hypothesis"))


def test_foreign_id_prefix_is_refused(strict):
    """`kind` alone would pass; the id would name a different entity."""
    _refuses(strict, _record(id="dataset:age"))


def test_status_outside_the_descriptor_is_refused(strict):
    """`archived` is valid for `hypothesis` and not for `concept` (profiles/core.py:426)."""
    _refuses(strict, _record(status="archived"))


def test_missing_status_is_refused(strict):
    record = _record()
    del record["status"]
    _refuses(strict, record)


def test_authored_schema_profile_is_refused(strict):
    """The narrowing: `profile` is the authored field, `schema_profile` its derived one."""
    _refuses(strict, _record(schema_profile=f"{BASE_NAME}/2.0+concept/1.0"))


def test_empty_promoted_from_is_refused(strict):
    """`minLength: 1` -- a promotion from nowhere is not a promotion."""
    _refuses(strict, _record(promoted_from=""))


def test_non_string_promoted_from_is_refused(strict):
    _refuses(strict, _record(promoted_from=3))


def test_scalar_related_is_refused(strict):
    _refuses(strict, _record(related="concept:immune-evasion"))


def test_non_string_related_item_is_refused(strict):
    _refuses(strict, _record(related=[3]))


# --- the mixin's own declaration -------------------------------------------------


def test_promoted_from_matches_the_frozen_oracle():
    assert _mixin()["properties"]["promoted_from"] == PROMOTED_FROM_ORACLE


def test_mixin_pins_its_own_kind():
    """Gate 2's requirement, asserted here too so the file is self-certifying."""
    assert _mixin()["properties"]["kind"] == {"const": "concept"}


def test_mixin_declares_exactly_the_frozen_field_set():
    """The step-1 inventory, as an assertion.

    A field added to the mixin without going through the inventory fails here -- which
    is the point. `schema_profile` is present as `false`, the reserved narrowing.
    """
    assert set(_mixin()["properties"]) == {
        "id",
        "kind",
        "status",
        "profile",
        "promoted_from",
        "related",
        "source_refs",
        "schema_profile",
    }
