"""Step 5 of the method slice: reconcile the schema against the Pydantic projection.

The contract is "the SCHEMA refuses what it does not know, the PROJECTION preserves
what it admitted". `method` is the first tranche kind where that is checked in BOTH
directions, because it is the only one with a typed subclass: `CORE_KIND_MODELS` maps
it to `MethodEntity`, so there is a kind-specific model opinion to reconcile against.

- **Schema admits X, projection drops X** -- a real defect for any kind. Checked below
  over every admitted field.
- **Model declares Y, schema never admits Y** -- for `concept` this direction was
  waived, because a field the generic `ProjectEntity` declares and a concept schema
  never admits (`taxon`, `datapackage`) is dead weight in a model shared with 29 other
  kinds, not an unvouched field. That waiver still applies to the 70 fields
  `MethodEntity` INHERITS. It does not apply to the two it ADDS: `stochasticity` and
  `seed_params` are declared for this kind specifically, and a schema that refused them
  would make the kind's own model unreachable. Those two are checked.

Six admitted fields survive only because `ProjectEntity` is `extra="allow"`. Five carry
no method records; `promoted_from` carries 20. That preservation is load-bearing and
currently accidental -- `Entity` itself is `extra="ignore"`, so a future tightening of
`MethodEntity` would silently drop the field 20 records use to record where they came
from. These tests are what makes that fail loudly.
"""

from __future__ import annotations

import json
from importlib.resources import files

import pytest

from science_tool.graph.entity_registry import EntityRegistry

_BASE = "science-entity-base-2.0.json"
_MIXIN = "mixin-method-1.0.json"


def _composed_properties() -> dict[str, object]:
    base = json.loads(files("science_model.schemas").joinpath(_BASE).read_text())
    mixin = json.loads(files("science_model.schemas").joinpath(_MIXIN).read_text())
    return {**base["properties"], **mixin["properties"]}


def _admitted() -> set[str]:
    return {name for name, spec in _composed_properties().items() if spec is not False}


def _method_class():
    return EntityRegistry.with_core_types().resolve_class("method")


# Values that satisfy each admitted field's declared type. Hand-written rather than
# generated from the schema: a generator would derive the input from the same document
# it is meant to be testing.
_SAMPLE: dict[str, object] = {
    "id": "method:null-model",
    "kind": "method",
    "title": "Null model",
    "status": "active",
    "created": "2026-06-10",
    "updated": "2026-06-10",
    "profile": "local",
    "promoted_from": "knowledge/sources/local/terms.yaml",
    "stochasticity": "seedable",
    "seed_params": ["random_state"],
    "related": ["task:t662"],
    "source_refs": ["cite:Wu2017MM3D"],
    "datasets": ["MMRF CoMMpass IA18/IA22"],
    "aliases": ["tool:metapredict"],
    "ontology_terms": ["MONDO:0005015"],
    "description": "Fast disorder predictor.",
    "tags": ["covariate"],
    "version": "1",
    "contributors": ["kh"],
    "licenses": ["CC0-1.0"],
    "sources": ["knowledge/sources/local/terms.yaml"],
    "same_as": ["method:null-model-v2"],
    "dataset_usage": [],
}

# What the loader supplies; `ProjectEntity` requires these but no author writes them.
_LOADER_SUPPLIED: dict[str, object] = {
    "project": "mm30",
    "content_preview": "",
    "file_path": "entities/methods/null-model.md",
}


def test_the_sample_covers_every_admitted_field():
    """Guards the guard: an admitted field with no sample would be silently unchecked."""
    assert _admitted() - set(_SAMPLE) == set()


@pytest.mark.parametrize("field", sorted(_admitted()))
def test_every_admitted_field_survives_projection(field):
    entity = _method_class().model_validate({**_SAMPLE, **_LOADER_SUPPLIED})
    dumped = entity.model_dump()
    assert field in dumped, (
        f"the composed schema admits {field!r} and the projection dropped it"
    )


def test_the_kind_specific_model_fields_are_admitted_by_the_schema():
    """The surplus direction, which only a TYPED kind can pose meaningfully.

    `stochasticity` and `seed_params` are what `MethodEntity` adds to `ProjectEntity`.
    A schema that admitted neither would still pass every corpus check -- no record
    authors them -- while making the shipped method-stochasticity program unauthorable.
    That is precisely the failure a corpus-only inventory cannot see.
    """
    from science_model.entities import MethodEntity, ProjectEntity

    kind_specific = set(MethodEntity.model_fields) - set(ProjectEntity.model_fields)
    assert kind_specific == {"stochasticity", "seed_params"}
    assert kind_specific <= _admitted(), (
        f"the model declares {sorted(kind_specific - _admitted())} for this kind and "
        "the schema never admits them"
    )


def test_the_inherited_surplus_is_deliberately_not_reconciled():
    """States the waiver as an assertion rather than leaving it as prose.

    `MethodEntity` inherits 70 fields from a model shared with 29 other kinds, and most
    are unreachable for this kind. This does not check them; it pins the SIZE of what is
    being waived, so the waiver cannot quietly grow to cover kind-specific fields.
    """
    from science_model.entities import MethodEntity, ProjectEntity

    inherited_unadmitted = set(ProjectEntity.model_fields) - _admitted()
    assert inherited_unadmitted, "expected inherited dead weight; found none"
    assert set(MethodEntity.model_fields) - set(ProjectEntity.model_fields) <= _admitted()


def test_promoted_from_is_preserved_as_an_extra():
    """The live case: 20 of 51 records. Named separately so a regression reads as
    itself, not as one parametrized id among twenty-three."""
    entity = _method_class().model_validate({**_SAMPLE, **_LOADER_SUPPLIED})
    assert entity.model_extra is not None
    assert entity.model_extra["promoted_from"] == "knowledge/sources/local/terms.yaml"


def test_stochasticity_projects_onto_the_enum():
    """Declared, not an extra -- the difference between the two admitted-field classes.

    `promoted_from` above survives via `extra="allow"`; this one is a real field with a
    real type, and the projection turns the authored string into the enum member the
    six production readers compare against.
    """
    from science_model.entities import Stochasticity

    entity = _method_class().model_validate({**_SAMPLE, **_LOADER_SUPPLIED})
    assert entity.stochasticity is Stochasticity.SEEDABLE
    assert entity.seed_params == ["random_state"]


def test_the_projection_still_allows_extras():
    """The mechanism the six undeclared-but-admitted fields depend on.

    `MethodEntity` subclasses `ProjectEntity`; if it ever declares its own
    `model_config`, this is the line that must be kept true -- or those six fields need
    declaring on it.
    """
    assert _method_class().model_config.get("extra") == "allow"


def test_schema_profile_is_the_only_narrowed_field():
    narrowed = {
        name for name, spec in _composed_properties().items() if spec is False
    }
    assert narrowed == {"schema_profile"}
