"""The concept SCHEMA and the concept PROJECTION, reconciled field by field.

The `hypothesis` counterpart of this file (`test_hypothesis_entity.py`) states the three
properties in full; this is the same reconciliation for `concept`, and the shape of the
battery is deliberately the same so the two read as one pattern rather than two.

One structural difference, and it is the reason this file exists rather than a
parametrization of the other: **`concept` has no typed subclass.** It projects onto the
generic `ProjectEntity`, so the shared surface is the intersection of the composed
schema with a 70-field model shared by 29 other untyped kinds. Six admitted fields
(`promoted_from`, `contributors`, `licenses`, `sources`, `tags`, `version`) fall
OUTSIDE that intersection: the model declares none of them and preserves them as
`extra="allow"` extras. They are not in the battery because there is no model opinion
to reconcile a schema opinion against -- their shapes are probed in
`test_mixin_concept_1_0.py`, and their survival in
`science/tests/test_concept_slice_contract_reconciliation.py`.

That includes `promoted_from`, the most concept-specific field of the lot. Its absence
here is not an oversight; it is what "admitted but undeclared" means.
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
    generation: default_profile_for_kind("concept", generation=generation)
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
    "project": "p",
    "file_path": "entities/concepts/age.md",
    "content_preview": "",
    "ontology_terms": [],
    "related": [],
    "source_refs": [],
}


def _payload(**over: Any) -> dict[str, Any]:
    base = {
        "id": "concept:age",
        "kind": "concept",
        "title": "Age",
        "status": "active",
        "created": "2026-06-10",
        "updated": "2026-06-10",
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
    # The mixin pins the prefix and the base pins the shape. `dataset:age` is the case the
    # prefix exists for: `kind: concept` would still pass while the id named another entity.
    "id": [42, "", "age", "dataset:age", "concept:age"],
    "kind": [42, "hypothesis", "Concept", "concept"],
    # The descriptor declares exactly two (profiles/core.py:426), and `mixin-concept-1.1`
    # deliberately does NOT enum-lock them: `concept` is not in `_CERTIFIED_KINDS`, so the
    # vocabulary is validate's WARN to report, not the schema's to refuse at load. Both
    # tests below still bind -- the model takes `status: str | None`, so a schema that
    # admits `archived` is not laxer than the model, and every admitted value must still
    # survive the projection. `42` is the shape control that keeps this row failable.
    "status": [42, "", "archived", "draft", "deprecated", "active"],
    "title": [42, "Age"],
    "created": [42, "2026-13-01", "2026-02-31", "06-10-2026", "2026-06-10"],
    "updated": [42, "not-a-date", "2026-06-10"],
    # 179 records carry it; `core` is ProjectEntity's DEFAULT and no record uses it.
    "profile": [42, "local", "project_specific", "core"],
    "related": [42, "concept:x", [42], ["concept:immune-evasion"]],
    "source_refs": [42, "paper:x", [42], ["paper:smith2021"]],
    # 37 records carry it, all empty. The empty list is the control, not an omission.
    "ontology_terms": [42, "MONDO:0005015", [42], [], ["MONDO:0005015"]],
    "description": [42, "A patient-level covariate."],
    "same_as": [42, "concept:years-old", [42], ["concept:years-old"]],
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
    assert not lax, (
        f"gen {generation}: the schema admits {field}={lax!r} that the model refuses"
    )


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
