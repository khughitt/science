"""The finding SCHEMA and the finding PROJECTION, reconciled field by field.

`test_hypothesis_entity.py` states the three properties in full; this is the same
reconciliation for `finding`, and the shape of the battery is deliberately the same so the
files read as one pattern rather than six.

Like `concept`, `search` and `observation`, **`finding` has no typed subclass.** It projects
onto the generic `ProjectEntity`, so the shared surface is the intersection of the composed
schema with a model shared by 29 other untyped kinds. SEVENTEEN entries, the largest battery
in the tranche, because the mixin admits five properties no earlier tranche mixin declared.

ELEVEN admitted fields fall OUTSIDE that intersection -- `contributors`, `input`,
`licenses`, `mode`, `observations`, `promoted_from`, `propositions`, `sources`,
`superseded_by`, `tags`, `version`. The model declares none of them, preserving them as
`extra="allow"` extras. They are not in the battery because there is no model opinion to
reconcile a schema opinion against; their shapes are probed in
`test_mixin_finding_1_0.py`, and their survival in
`science/tests/test_finding_slice_contract_reconciliation.py`.

**Five of those eleven are carried by real records** (`promoted_from` 26, `propositions` 25,
`observations` 25, `mode` 23, `input` 22), where `observation`'s equivalent set had one.
A battery's size and the shape of its complement are per-kind derivations, never tranche
constants -- which is why `test_the_BATTERY_is_EXACTLY_the_shared_surface` asserts equality
rather than coverage.

`status` is the entry to read carefully. Its battery row looks identical whether or not the
schema enum-locks the field -- every value is a string -- which is exactly how
`mixin-concept-1.0`'s premature enum survived its own certification. The ruling is asserted
by name in `test_the_status_shape_is_checked_without_the_vocabulary` below rather than left
to this battery to imply. After the source migration all 201 records are `active`, so the
corpus varies this field not at all.
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
    generation: default_profile_for_kind("finding", generation=generation)
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
#
# `file_path` is the exception, and it appears in BOTH this block and the battery. The model
# requires it, so it must have a default here or every row fails for a missing field rather
# than for the value under test. It is ALSO a real schema field for this kind alone -- the
# 149 structured rows author `source_path` and `normalize_structured_row` renames it -- so
# it is genuinely reconcilable and belongs in the battery too. `_model_payload` layers
# `_payload` second, so a battery row's value wins over this default.
_MODEL_ONLY: dict[str, Any] = {
    "project": "natural-systems",
    "file_path": "entities/findings/0005-equiv-calibration-full.md",
    "content_preview": "",
    "ontology_terms": [],
    "related": [],
    "source_refs": [],
}


def _payload(**over: Any) -> dict[str, Any]:
    base = {
        "id": "finding:0005-equiv-calibration-full",
        "kind": "finding",
        "title": "Full equivalence calibration calibrates 71/74 strata",
        "status": "active",
        "created": "2026-06-21",
        "updated": "2026-06-21",
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


# Fields whose model type MATERIALIZES a declared default on projection, so the dumped value
# is a superset of the authored one rather than equal to it. `relations` is the only such
# field in this battery: `AuthoredTargetedRelation` declares
# `graph_layer: str = "graph/knowledge"`, so an authored `{predicate, target}` dumps with a
# third key.
#
# This is NOT a preservation failure and the distinction matters. Preservation means the
# author's values survive; a declared default being filled in adds information the model
# owns and loses none the author wrote. Earlier tranche batteries never hit this because
# none of them admitted a field whose items are typed objects -- so the strict equality they
# use is correct for them and would be wrong here.
_MODEL_DEFAULTS_MATERIALIZED: dict[str, set[str]] = {"relations": {"graph_layer"}}


def _model_preserves(field: str, value: Any) -> bool:
    try:
        entity = ProjectEntity.model_validate(_model_payload(**{field: value}))
    except ValidationError:
        return False
    # `mode="json"` for the reason `test_hypothesis_entity.py` uses it: `created`/`updated`
    # are `datetime.date` on the model, so a plain dump compares a date object against the
    # authored ISO string and reports preservation loss where there is none.
    dumped = entity.model_dump(mode="json")
    if field not in dumped:
        return False
    if field not in _MODEL_DEFAULTS_MATERIALIZED:
        return dumped[field] == value
    allowed = _MODEL_DEFAULTS_MATERIALIZED[field]
    for authored_item, dumped_item in zip(value, dumped[field], strict=True):
        if any(dumped_item.get(k) != v for k, v in authored_item.items()):
            return False  # an authored value was changed or dropped
        if set(dumped_item) - set(authored_item) - allowed:
            return False  # a key appeared that is not a declared default
    return True


# Every value here is one the MODEL has an opinion about; the point is to make the schema
# hold the same opinions. Must equal `_SHARED_BY_GENERATION[generation]` exactly, both
# directions -- see `test_the_BATTERY_is_EXACTLY_the_shared_surface`.
_BATTERY: dict[str, list[Any]] = {
    # The mixin pins the prefix and the base pins the shape. `observation:...` is the case
    # the prefix exists for: `kind: finding` would still pass while the id named another
    # entity -- and `observation` is the realistic confusion, since a finding's own
    # `observations:` list names records of exactly that kind.
    "id": [42, "", "0005-equiv", "observation:0005-equiv", "finding:0005-equiv"],
    "kind": [42, "observation", "Finding", "finding"],
    # The descriptor declares four (profiles/core.py:155) and the mixin deliberately does
    # NOT enum-lock them -- `finding` is not in `_CERTIFIED_KINDS`. `42` and `[]` are the
    # shape controls that keep this row failable; see the named ruling test below.
    "status": [42, [], "superseded", "retired", "archived", "proposed", "active"],
    "title": [42, "Full equivalence calibration"],
    "created": [42, "2026-13-01", "2026-02-31", "21-06-2026", "2026-06-21"],
    "updated": [42, "not-a-date", "2026-06-21"],
    # 44 of 52 markdown records carry `related`; every structured row gets one backfilled.
    "related": [42, "hypothesis:0007-fidelity", [42], [], ["hypothesis:0007-fidelity"]],
    "source_refs": [42, "dataset:arxiv-equiv", [42], [], ["dataset:arxiv-equiv"]],
    # Authored by 26 protein-landscape records AND backfilled onto all 149 structured rows.
    "aliases": [42, "f05", [42], [], ["f05"]],
    # Authored by every one of the 149 structured rows, by no markdown record.
    "evidence_refs": [42, "limit-relation:asep__a", [42], [], ["limit-relation:asep__a"]],
    # Authored on BOTH paths -- 26 markdown, 149 structured -- and defaulted into `raw` by
    # the loader when omitted.
    "profile": [42, [], "local", "project_specific"],
    # The one field no earlier tranche kind admits. Authored as `source_path` on the
    # structured path and renamed by `normalize_structured_row`; `minLength: 1` is what
    # the empty-string control below exercises.
    "file_path": [42, "", "knowledge/sources/project_specific/finding.yaml"],
    # 3 records, all `sci:amends`. The `note` entry is the corpus migration: the schema
    # refuses it now, where `AuthoredTargetedRelation` used to discard it silently.
    "relations": [
        42,
        [{"predicate": "sci:amends"}],
        [{"predicate": "sci:amends", "target": "finding:0016-x", "note": "why"}],
        [],
        [{"predicate": "sci:amends", "target": "finding:0016-x"}],
    ],
    # No finding record carries `ontology_terms` in frontmatter, but every structured row
    # gets an empty list backfilled. Base 2.0 admits it; the empty list keeps the row
    # failable rather than being an omission.
    "ontology_terms": [42, "MONDO:0005015", [42], [], ["MONDO:0005015"]],
    # 26 markdown records and all 149 structured rows carry `description`.
    "description": [42, "A unit of learned knowledge."],
    "same_as": [42, "finding:0004-equiv-pilot", [42], ["finding:0004-equiv-pilot"]],
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
def test_every_battery_row_has_a_refusal_and_an_admission(generation: int) -> None:
    """A row where the schema accepts everything reconciles nothing.

    This is the guard that would have caught a battery written to pass: without it, a row
    listing only valid values is indistinguishable from a field with no constraints.
    """
    profile = _PROFILE_BY_GENERATION[generation]
    for field, values in _BATTERY.items():
        verdicts = {_schema_accepts(field, value, profile) for value in values}
        assert verdicts == {True, False}, (
            f"gen {generation} field {field!r}: schema verdicts are {verdicts}; "
            "every row needs at least one value the schema refuses and one it admits"
        )


@pytest.mark.parametrize("generation", _GENERATIONS)
def test_the_model_agrees_with_the_schema_on_every_admitted_value(generation: int) -> None:
    """The reconciliation itself: a value the schema admits must project and survive."""
    profile = _PROFILE_BY_GENERATION[generation]
    for field, values in _BATTERY.items():
        for value in values:
            if not _schema_accepts(field, value, profile):
                continue
            assert _model_accepts(field, value), (
                f"gen {generation}: schema admits {field}={value!r} and the model refuses it"
            )
            assert _model_preserves(field, value), (
                f"gen {generation}: schema admits {field}={value!r} and projection drops it"
            )


def test_the_status_shape_is_checked_without_the_vocabulary() -> None:
    """The ruling, asserted by name rather than left to the battery to imply.

    The mixin constrains `status` to a string and does NOT enum-lock the descriptor's four
    values, because `finding` is not in `_CERTIFIED_KINDS` and a schema enum refuses a
    record at load with no warning stage. `proposed` is not in the descriptor's list and is
    admitted here on purpose: that is what "shape, not vocabulary" means.
    """
    profile = _PROFILE_BY_GENERATION[3]
    assert _schema_accepts("status", "proposed", profile)
    assert _schema_accepts("status", "superseded", profile)
    assert not _schema_accepts("status", 42, profile)
    assert not _schema_accepts("status", [], profile)


def test_the_eleven_admitted_fields_outside_the_battery_are_a_decision() -> None:
    """Why this battery is 17 entries and not 28, stated rather than left to arithmetic.

    Each is admitted by the schema and declared by no model field, so there is no model
    opinion for the battery to reconcile against. They are not absent from the contract --
    shape is checked in `test_mixin_finding_1_0.py`, preservation in
    `science/tests/test_finding_slice_contract_reconciliation.py`. Asserting the set here
    keeps the omission a decision rather than a gap someone closes by accident.
    """
    outside = _ADMITTED_BY_GENERATION[3] - _SHARED_BY_GENERATION[3]
    assert outside == {
        "contributors",
        "input",
        "licenses",
        "mode",
        "observations",
        "promoted_from",
        "propositions",
        "sources",
        "superseded_by",
        "tags",
        "version",
    }


def test_both_generations_resolve_the_same_profile() -> None:
    """Unlike earlier tranche kinds, BOTH rows carry real corpus for this kind: 172 of the
    201 records live in a generation-2 project and the other 29 in generation-3 ones."""
    assert (
        _PROFILE_BY_GENERATION[2].render()
        == _PROFILE_BY_GENERATION[3].render()
        == "science-entity-base/2.0+finding/1.0"
    )


def test_the_relations_default_is_an_ADDITION_not_a_substitution() -> None:
    """Pins `_MODEL_DEFAULTS_MATERIALIZED`'s premise instead of trusting the exemption.

    Without this, the relaxed preservation rule above would be an unfalsifiable escape
    hatch: any projection change to `relations` would pass as "a default was materialized".
    Here the authored keys are asserted to survive UNCHANGED and the added key is asserted
    to be exactly `graph_layer` with exactly the model's declared default.
    """
    authored = {"predicate": "sci:amends", "target": "finding:0016-x"}
    entity = ProjectEntity.model_validate(_model_payload(relations=[authored]))
    dumped = entity.model_dump(mode="json")["relations"]

    assert len(dumped) == 1
    assert dumped[0]["predicate"] == "sci:amends"
    assert dumped[0]["target"] == "finding:0016-x"
    assert set(dumped[0]) - set(authored) == {"graph_layer"}
    assert dumped[0]["graph_layer"] == "graph/knowledge"


def test_an_authored_graph_layer_is_not_overwritten_by_the_default() -> None:
    """The other half: materializing a default must never SUBSTITUTE for an authored value."""
    authored = {
        "predicate": "sci:amends",
        "target": "finding:0016-x",
        "graph_layer": "graph/local",
    }
    entity = ProjectEntity.model_validate(_model_payload(relations=[authored]))
    assert entity.model_dump(mode="json")["relations"][0]["graph_layer"] == "graph/local"
