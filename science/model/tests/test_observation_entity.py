"""The observation SCHEMA and the observation PROJECTION, reconciled field by field.

`test_hypothesis_entity.py` states the three properties in full; this is the same
reconciliation for `observation`, and the shape of the battery is deliberately the same so
the files read as one pattern rather than five.

Like `concept` and `search`, **`observation` has no typed subclass.** It projects onto the
generic `ProjectEntity`, so the shared surface is the intersection of the composed schema
with a model shared by 29 other untyped kinds. SIX admitted fields fall OUTSIDE that
intersection -- `contributors`, `licenses`, `promoted_from`, `sources`, `tags`, `version` --
and the model declares none of them, preserving them as `extra="allow"` extras. They are not
in the battery because there is no model opinion to reconcile a schema opinion against;
their shapes are probed in `test_mixin_observation_1_0.py`, and their survival in
`science/tests/test_observation_slice_contract_reconciliation.py`.

**`promoted_from` is the one to notice.** It is the only field in that six that a real record
carries (14 of 21), and it is why this battery has 12 entries where `search`'s has 13: the
two kinds differ in `profile` and `promoted_from`, in opposite directions. A battery's size
is a per-kind derivation, never a tranche constant -- which is why
`test_the_BATTERY_is_EXACTLY_the_shared_surface` asserts equality rather than coverage.

`status` is the entry to read carefully. Its battery row looks identical whether or not the
schema enum-locks the field -- every value is a string -- which is exactly how
`mixin-concept-1.0`'s premature enum survived its own certification. The ruling is asserted
by name in `test_the_status_shape_is_checked_without_the_vocabulary` below rather than left
to this battery to imply. This kind is the tranche's sharpest case: all 21 records are
`active` AND they all live in one project, so there is not even a second author who could
have diverged.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError
from science_model.entities import ProjectEntity
from science_model.entity_schema import (
    EntityValidationError,
    EntityValidator,
    ProfileString,
    admitted_field_names,
    default_profile_for_kind,
)

_GENERATIONS = (2, 3)
_PROFILE_BY_GENERATION = {
    generation: default_profile_for_kind("observation", generation=generation)
    for generation in _GENERATIONS
}
_V = EntityValidator()

_ADMITTED_BY_GENERATION = {
    generation: admitted_field_names(profile)
    for generation, profile in _PROFILE_BY_GENERATION.items()
}

_SHARED_BY_GENERATION = {
    generation: admitted & set(ProjectEntity.model_fields)
    for generation, admitted in _ADMITTED_BY_GENERATION.items()
}

# Required by `ProjectEntity` and stamped by the loader, never authored in frontmatter.
_MODEL_ONLY: dict[str, Any] = {
    "project": "cycles",
    "file_path": "entities/observations/swan-stage-cardiometabolic-shift.md",
    "content_preview": "",
    "ontology_terms": [],
    "related": [],
    "source_refs": [],
}


def _payload(**over: Any) -> dict[str, Any]:
    base = {
        "id": "observation:swan-stage-cardiometabolic-shift",
        "kind": "observation",
        "title": "Natural postmenopause shifts lipids net of chronological age (SWAN)",
        "status": "active",
        "created": "2026-04-01",
        "updated": "2026-04-01",
    }
    base.update(over)
    return base


def _model_payload(**over: Any) -> dict[str, Any]:
    return _MODEL_ONLY | _payload(**over)


def _schema_accepts(field: str, value: Any, profile: ProfileString) -> bool:
    try:
        _V.validate_as(_payload(**{field: value}), profile)
        return True
    except EntityValidationError:
        return False


def _model_accepts(field: str, value: Any) -> bool:
    try:
        ProjectEntity.model_validate(_model_payload(**{field: value}))
        return True
    except ValidationError:
        return False


def _model_preserves(field: str, value: Any) -> bool:
    try:
        entity = ProjectEntity.model_validate(_model_payload(**{field: value}))
    except ValidationError:
        return False
    # `mode="json"` for the reason `test_hypothesis_entity.py` uses it: `created`/`updated`
    # are `datetime.date` on the model, so a plain dump compares a date object against the
    # authored ISO string and reports preservation loss where there is none. The comparison
    # must be against what the AUTHOR wrote.
    dumped = entity.model_dump(mode="json")
    return field in dumped and dumped[field] == value


# Every value here is one the MODEL has an opinion about; the point is to make the schema
# hold the same opinions. Must equal `_SHARED_BY_GENERATION[generation]` exactly, both
# directions -- see `test_the_BATTERY_is_EXACTLY_the_shared_surface`.
_BATTERY: dict[str, list[Any]] = {
    # The mixin pins the prefix and the base pins the shape. `finding:swan-...` is the case
    # the prefix exists for: `kind: observation` would still pass while the id named another
    # entity -- and `finding` is the realistic confusion here, since both kinds are epistemic
    # and this project holds records of each.
    "id": [42, "", "swan-shift", "finding:swan-shift", "observation:swan-shift"],
    "kind": [42, "finding", "Observation", "observation"],
    # The descriptor declares three (profiles/core.py:150) and the mixin deliberately does
    # NOT enum-lock them -- `observation` is not in `_CERTIFIED_KINDS`. `42` and `[]` are the
    # shape controls that keep this row failable; see the named ruling test below.
    "status": [42, [], "archived", "retired", "proposed", "active"],
    "title": [42, "Postmenopause shifts lipids net of age"],
    "created": [42, "2026-13-01", "2026-02-31", "01-04-2026", "2026-04-01"],
    "updated": [42, "not-a-date", "2026-04-01"],
    # 21 of 21 carry both, and every value in the corpus is a list of strings.
    "related": [42, "hypothesis:0002-rhythm", [42], ["hypothesis:0002-rhythm"]],
    "source_refs": [42, "dataset:swan", [42], ["dataset:swan"]],
    # NO observation record carries `ontology_terms`, though 411 records in this project do
    # on other kinds. Base 2.0 admits it, so the empty list is the control that keeps the row
    # failable rather than an omission.
    "ontology_terms": [42, "MONDO:0005015", [42], [], ["MONDO:0005015"]],
    # The retired aggregate's rows carried `description`; promotion moved it into the BODY,
    # so no record carries it in frontmatter. Base 2.0 admits it either way.
    "description": [42, "A concrete empirical fact anchored to specific data."],
    "same_as": [42, "observation:swan-age-slope", [42], ["observation:swan-age-slope"]],
    "dataset_usage": [42, "x", []],
}


@pytest.mark.parametrize("generation", _GENERATIONS)
def test_the_BATTERY_is_EXACTLY_the_shared_surface(generation: int) -> None:
    """EQUALITY, not coverage, and in both directions.

    `_SHARED_BY_GENERATION` is derived and the battery is hand-written, so the battery is
    the half that falls behind: a missing entry is a field both authorities describe and
    neither reconciles, and a spurious one reads like coverage that never runs.
    """
    shared = _SHARED_BY_GENERATION[generation]
    assert set(_BATTERY) == shared, (
        f"gen {generation} unreconciled: {sorted(shared - set(_BATTERY))}; "
        f"stale: {sorted(set(_BATTERY) - shared)}"
    )


def test_promoted_from_is_admitted_but_OUTSIDE_the_battery() -> None:
    """Why this battery is 12 entries and not 13, stated rather than left to arithmetic.

    The field is admitted by the schema and declared by no model field, so there is no
    model opinion for the battery to reconcile against. It is not absent from the contract
    -- it is checked on the other two axes: shape in `test_mixin_observation_1_0.py`,
    preservation in `test_observation_slice_contract_reconciliation.py`. Asserting it here
    keeps the omission a decision rather than a gap someone closes by accident.
    """
    for generation in _GENERATIONS:
        assert "promoted_from" in _ADMITTED_BY_GENERATION[generation]
        assert "promoted_from" not in _SHARED_BY_GENERATION[generation]
    assert "promoted_from" not in _BATTERY


@pytest.mark.parametrize("generation", _GENERATIONS)
@pytest.mark.parametrize("field", sorted(_BATTERY))
def test_the_schema_is_at_least_as_strict_as_the_model(generation: int, field: str) -> None:
    """Else the model is the real authority and the schema is decoration."""
    profile = _PROFILE_BY_GENERATION[generation]
    lax = [
        value
        for value in _BATTERY[field]
        if _schema_accepts(field, value, profile) and not _model_accepts(field, value)
    ]
    assert not lax, f"gen {generation}: the schema admits {field}={lax!r} that the model refuses"


@pytest.mark.parametrize("generation", _GENERATIONS)
@pytest.mark.parametrize("field", sorted(_BATTERY))
def test_every_value_the_schema_ADMITS_SURVIVES_the_projection(
    generation: int, field: str
) -> None:
    """Acceptance and preservation are different properties.

    A field that validates on disk and evaporates on load is not a contract but a trap.
    """
    profile = _PROFILE_BY_GENERATION[generation]
    for value in _BATTERY[field]:
        if not _schema_accepts(field, value, profile):
            continue
        assert _model_preserves(field, value), (
            f"gen {generation}: schema admits {field}={value!r}, projection lost it"
        )


@pytest.mark.parametrize("generation", _GENERATIONS)
def test_the_battery_actually_exercises_refusal(generation: int) -> None:
    """Guards the battery itself.

    Every entry above must contain at least one value the schema REFUSES and at least one
    it ADMITS. An all-accepted entry reconciles nothing and would sit here reading like
    coverage -- the failure mode the equality test cannot see.
    """
    profile = _PROFILE_BY_GENERATION[generation]
    inert = [
        field
        for field, values in _BATTERY.items()
        if all(_schema_accepts(field, v, profile) for v in values)
        or not any(_schema_accepts(field, v, profile) for v in values)
    ]
    assert not inert, f"gen {generation}: entries with no accept/refuse contrast: {inert}"


@pytest.mark.parametrize("generation", _GENERATIONS)
def test_the_status_shape_is_checked_without_the_vocabulary(generation: int) -> None:
    """The slice ruling, stated where the battery would otherwise hide it.

    `status` is the one field whose battery row would look identical whether or not the
    schema enum-locked it -- `archived`, `proposed` and `active` are all strings. This
    names the property directly: every descriptor status AND two statuses outside the
    vocabulary are admitted, while a non-string is not.

    All 21 corpus records are `active`, so no corpus-derived probe can make this
    distinction. That uniformity is precisely what let `mixin-concept-1.0` ship a
    premature enum -- and here it is total, since one project root owns every record.
    """
    profile = _PROFILE_BY_GENERATION[generation]
    for value in ("active", "retired", "archived", "proposed", "draft"):
        assert _schema_accepts("status", value, profile), value
    assert not _schema_accepts("status", 42, profile)


@pytest.mark.parametrize("generation", _GENERATIONS)
def test_both_generations_resolve_the_same_profile(generation: int) -> None:
    """The two rows armed together, asserted where the battery consumes them.

    Every test above is parametrized over both generations, so a row-3-only arming would
    make half of them error rather than fail -- which reads as breakage, not as a ruling.
    """
    assert (
        _PROFILE_BY_GENERATION[generation].render()
        == "science-entity-base/2.0+observation/1.0"
    )
