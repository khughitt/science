"""The method SCHEMA and the method PROJECTION, reconciled field by field.

The `hypothesis` counterpart (`test_hypothesis_entity.py`) states the three properties
in full; this is the same reconciliation for `method`, and the shape of the battery is
deliberately the same so they read as one pattern rather than three.

`method` is the only tranche kind with a typed subclass. `CORE_KIND_MODELS` maps it to
`MethodEntity`, so the shared surface below is the intersection of the composed schema
with `MethodEntity` -- 17 fields, including the two this kind adds (`stochasticity`,
`seed_params`) that no other tranche kind has to reconcile.

Six admitted fields fall OUTSIDE that intersection (`promoted_from`, `contributors`,
`licenses`, `sources`, `tags`, `version`): the model declares none of them and preserves
them as `extra="allow"` extras. They are not in the battery because there is no model
opinion to reconcile a schema opinion against -- their shapes are probed in
`test_mixin_method_1_0.py`, and their survival in
`science/tests/test_method_slice_contract_reconciliation.py`.

That includes `promoted_from`, which 20 of the 51 records carry. Its absence here is not
an oversight; it is what "admitted but undeclared" means.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError
from science_model.entities import MethodEntity
from science_model.entity_schema import (
    EntityValidationError,
    EntityValidator,
    ProfileString,
    admitted_field_names,
    default_profile_for_kind,
)

_GENERATIONS = (2, 3)
_PROFILE_BY_GENERATION = {
    generation: default_profile_for_kind("method", generation=generation)
    for generation in _GENERATIONS
}
_V = EntityValidator()

_ADMITTED_BY_GENERATION = {
    generation: admitted_field_names(profile)
    for generation, profile in _PROFILE_BY_GENERATION.items()
}

_SHARED_BY_GENERATION = {
    generation: admitted & set(MethodEntity.model_fields)
    for generation, admitted in _ADMITTED_BY_GENERATION.items()
}

# Required by `ProjectEntity` and stamped by the loader, never authored in frontmatter.
_MODEL_ONLY: dict[str, Any] = {
    "project": "p",
    "file_path": "entities/methods/null-model.md",
    "content_preview": "",
    "ontology_terms": [],
    "related": [],
    "source_refs": [],
}


def _payload(**over: Any) -> dict[str, Any]:
    base = {
        "id": "method:null-model",
        "kind": "method",
        "title": "Null model",
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
        MethodEntity.model_validate(_model_payload(**{field: value}))
        return True
    except ValidationError:
        return False


def _model_preserves(field: str, value: Any) -> bool:
    try:
        entity = MethodEntity.model_validate(_model_payload(**{field: value}))
    except ValidationError:
        return False
    # `mode="json"` for the reason `test_hypothesis_entity.py` uses it: `created`/`updated`
    # are `datetime.date` on the model, so a plain dump compares a date object against the
    # authored ISO string and reports preservation loss where there is none. It matters for
    # `stochasticity` too -- that one projects onto a StrEnum member, not the authored str.
    dumped = entity.model_dump(mode="json")
    return field in dumped and dumped[field] == value


# Every value here is one the MODEL has an opinion about; the point is to make the schema
# hold the same opinions. Must equal `_SHARED_BY_GENERATION[generation]` exactly, both
# directions -- see `test_the_BATTERY_is_EXACTLY_the_shared_surface`.
_BATTERY: dict[str, list[Any]] = {
    # The mixin pins the prefix and the base pins the shape. `dataset:null-model` is the
    # case the prefix exists for: `kind: method` would still pass while the id named
    # another entity.
    "id": [42, "", "null-model", "dataset:null-model", "method:null-model"],
    "kind": [42, "concept", "Method", "method"],
    # NO enum, per the slice ruling: `method` is not in `_CERTIFIED_KINDS`, so the schema
    # checks the SHAPE and leaves the vocabulary to `method.status-vocabulary`. `proposed`
    # is admitted deliberately -- cbioportal authors it. `42` is the contrast.
    "status": [42, "", "proposed", "archived", "active"],
    "title": [42, "Null model"],
    "created": [42, "2026-13-01", "2026-02-31", "06-10-2026", "2026-06-10"],
    "updated": [42, "not-a-date", "2026-06-10"],
    # 4 records carry it, all `local`. `core` is ProjectEntity's DEFAULT and no record uses it.
    "profile": [42, "local", "core"],
    "related": [42, "task:t662", [42], ["task:t662"]],
    "source_refs": [42, "cite:x", [42], ["cite:Wu2017MM3D"]],
    "datasets": [42, "MMRF", [42], [], ["MMRF CoMMpass IA18/IA22"]],
    "aliases": [42, "tool:metapredict", [42], ["tool:metapredict"]],
    # 12 records carry it. The empty list is the control, not an omission.
    "ontology_terms": [42, "MONDO:0005015", [42], [], ["MONDO:0005015"]],
    "description": [42, "Fast disorder predictor."],
    "same_as": [42, "method:null-model-v2", [42], ["method:null-model-v2"]],
    "dataset_usage": [42, "x", []],
    # The two fields this kind ADDS, and the reason it is the only tranche kind with a
    # meaningful surplus direction. Zero records author either. `null` is refused by the
    # schema on purpose -- absence already means unclassified.
    "stochasticity": [
        42,
        "",
        None,
        "mostly-deterministic",
        "deterministic",
        "seedable",
        "nondeterministic",
    ],
    "seed_params": [42, "random_state", [42], [], ["random_state", "seed"]],
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


@pytest.mark.parametrize("generation", _GENERATIONS)
def test_the_status_shape_is_checked_without_the_vocabulary(generation: int) -> None:
    """The slice ruling, stated where the battery could otherwise hide it.

    `status` is the one field whose battery entry would look identical whether or not the
    schema enum-locked it -- both `proposed` and `archived` are strings. This names the
    property directly: every descriptor status AND the one out-of-vocabulary status the
    corpus authors are admitted, while a non-string is not.
    """
    profile = _PROFILE_BY_GENERATION[generation]
    for value in ("active", "superseded", "retired", "archived", "proposed"):
        assert _schema_accepts("status", value, profile), value
    assert not _schema_accepts("status", 42, profile)
