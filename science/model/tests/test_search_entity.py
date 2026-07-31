"""The search SCHEMA and the search PROJECTION, reconciled field by field.

`test_hypothesis_entity.py` states the three properties in full; this is the same
reconciliation for `search`, and the shape of the battery is deliberately the same so
the files read as one pattern rather than four.

Like `concept`, **`search` has no typed subclass.** It projects onto the generic
`ProjectEntity`, so the shared surface is the intersection of the composed schema with a
model shared by 29 other untyped kinds. Five admitted fields (`contributors`, `licenses`,
`sources`, `tags`, `version`) fall OUTSIDE that intersection: the model declares none of
them and preserves them as `extra="allow"` extras. They are not in the battery because
there is no model opinion to reconcile a schema opinion against -- their shapes are
probed in `test_mixin_search_1_0.py`, and their survival in
`science/tests/test_search_slice_contract_reconciliation.py`.

`status` is the entry to read carefully. Its battery row looks identical whether or not
the schema enum-locks the field -- every value is a string -- which is exactly how
`mixin-concept-1.0`'s premature enum survived its own certification. The ruling is
asserted by name in `test_the_status_shape_is_checked_without_the_vocabulary` below
rather than left to this battery to imply.
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
    generation: default_profile_for_kind("search", generation=generation)
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
    "file_path": "entities/searches/0001-bulk-sc-integration-methods.md",
    "content_preview": "",
    "ontology_terms": [],
    "related": [],
    "source_refs": [],
}


def _payload(**over: Any) -> dict[str, Any]:
    base = {
        "id": "search:0001-bulk-sc-integration-methods",
        "kind": "search",
        "title": "Methods for integrating single-cell and bulk RNA-seq data",
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
    # The mixin pins the prefix and the base pins the shape. `method:0001-...` is the case
    # the prefix exists for: `kind: search` would still pass while the id named another
    # entity.
    "id": [42, "", "0001-meta", "method:0001-meta", "search:0001-meta"],
    "kind": [42, "concept", "Search", "search"],
    # The descriptor declares four (profiles/core.py:569) and the mixin deliberately does
    # NOT enum-lock them -- `search` is not in `_CERTIFIED_KINDS`. `42` and `[]` are the
    # shape controls that keep this row failable; see the named ruling test below.
    "status": [42, [], "archived", "proposed", "complete", "active"],
    "title": [42, "Meta-analysis methodology"],
    "created": [42, "2026-13-01", "2026-02-31", "01-04-2026", "2026-04-01"],
    "updated": [42, "not-a-date", "2026-04-01"],
    # NO search record authors `profile`, and -- CORRECTED by the observation slice
    # (2026-07-30) -- the loader does NOT inject it into the validated key set either. The
    # `setdefault("profile", ...)` this comment used to cite is on the STRUCTURED-row path,
    # and enrichment runs after `validate_against_schema` regardless, so nothing it adds can
    # face the schema. Instrumenting the validator on a real gen-3 load gives the validated
    # key set as the authored frontmatter minus exactly {canonical_id, content, file_path}.
    # The mixin's admission is therefore unjustified rather than wrong -- it admits a key
    # nothing authors -- and removing a field needs a version bump on its own grounds. The
    # row stays because the schema does admit it; only the reason has changed.
    "profile": [42, "local", "project_specific", "core"],
    "related": [42, "task:t021", [42], ["task:t021"]],
    "source_refs": [42, "paper:x", [42], ["paper:survey-attractor-topology-methods"]],
    # One of the 36 carries it, and empty. The empty list is the control, not an omission.
    "ontology_terms": [42, "MONDO:0005015", [42], [], ["MONDO:0005015"]],
    "description": [42, "A recorded literature search."],
    "same_as": [42, "search:0002-existing", [42], ["search:0002-existing"]],
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
    names the property directly: every descriptor status AND a status outside the
    vocabulary are admitted, while a non-string is not.

    All 36 corpus records are `active`, so no corpus-derived probe can make this
    distinction. That uniformity is precisely what let `mixin-concept-1.0` ship a
    premature enum.
    """
    profile = _PROFILE_BY_GENERATION[generation]
    for value in ("active", "complete", "retired", "archived", "proposed"):
        assert _schema_accepts("status", value, profile), value
    assert not _schema_accepts("status", 42, profile)
