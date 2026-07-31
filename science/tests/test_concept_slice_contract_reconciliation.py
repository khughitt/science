"""Step 5 of the concept slice: reconcile the schema against the Pydantic projection.

The contract is "the SCHEMA refuses what it does not know, the PROJECTION preserves
what it admitted". This module checks that in the direction where a violation is a
defect: **every field the composed schema admits must survive projection.**

The other direction is not checked, and deliberately so. `concept` has no typed
subclass -- `CORE_KIND_MODELS` has no entry, so it projects onto the generic
`ProjectEntity`, 70 fields shared with 29 other untyped kinds. A field `ProjectEntity`
declares that the concept schema never admits (`taxon`, `datapackage`, `benchmark`)
is unreachable for this kind: dead weight in a shared model, not an unvouched field.
Requiring an explanation for each would mean writing the same sentence 50+ times, and
the slice procedure's "unexplained fields on either side" was written against
`hypothesis`, whose projection is kind-specific.

Six admitted fields survive on `extra="allow"`. Five carry no concept records;
`promoted_from` carries 132, so that preservation is load-bearing.

CORRECTION (2026-07-30, found by mutation-testing the search slice's copy of this
paragraph): this previously said the preservation was "currently accidental -- `Entity`
itself is `extra="ignore"`". **That is false.** `Entity` sets
`model_config = ConfigDict(extra="allow")` (entities.py:325) and its docstring cites
D3.3: *"Never return to `extra='ignore'` -- that is the original defect."* `ProjectEntity`
inherits it, so preservation is a ruling rather than an accident. The risk these tests
guard is a subclass that explicitly overrides `model_config`, which D3.3 forbids.
"""

from __future__ import annotations

import json
from importlib.resources import files

import pytest

from science_tool.graph.entity_registry import EntityRegistry

_BASE = "science-entity-base-2.0.json"
_MIXIN = "mixin-concept-1.1.json"


def _composed_properties() -> dict[str, object]:
    base = json.loads(files("science_model.schemas").joinpath(_BASE).read_text())
    mixin = json.loads(files("science_model.schemas").joinpath(_MIXIN).read_text())
    return {**base["properties"], **mixin["properties"]}


def _admitted() -> set[str]:
    return {name for name, spec in _composed_properties().items() if spec is not False}


def _concept_class():
    return EntityRegistry.with_core_types().resolve_class("concept")


# Values that satisfy each admitted field's declared type. Hand-written rather than
# generated from the schema: a generator would derive the input from the same document
# it is meant to be testing.
_SAMPLE: dict[str, object] = {
    "id": "concept:age",
    "kind": "concept",
    "title": "Age",
    "status": "active",
    "created": "2026-06-10",
    "updated": "2026-06-10",
    "profile": "local",
    "promoted_from": "knowledge/sources/local/terms.yaml",
    "related": ["concept:immune-evasion"],
    "source_refs": ["paper:smith2021"],
    "ontology_terms": ["MONDO:0005015"],
    "description": "A patient-level covariate.",
    "tags": ["covariate"],
    "version": "1",
    "contributors": ["kh"],
    "licenses": ["CC0-1.0"],
    "sources": ["knowledge/sources/local/terms.yaml"],
    "same_as": ["concept:years-old"],
    "dataset_usage": [],
}

# What the loader supplies; `ProjectEntity` requires these but no author writes them.
_LOADER_SUPPLIED: dict[str, object] = {
    "project": "mm30",
    "content_preview": "",
    "file_path": "entities/concepts/age.md",
}


def test_the_sample_covers_every_admitted_field():
    """Guards the guard: an admitted field with no sample would be silently unchecked."""
    assert _admitted() - set(_SAMPLE) == set()


@pytest.mark.parametrize("field", sorted(_admitted()))
def test_every_admitted_field_survives_projection(field):
    entity = _concept_class().model_validate({**_SAMPLE, **_LOADER_SUPPLIED})
    dumped = entity.model_dump()
    assert field in dumped, (
        f"the composed schema admits {field!r} and the projection dropped it"
    )


def test_promoted_from_is_preserved_as_an_extra():
    """The live case. Named separately so a regression reads as itself, not as one
    parametrized id among nineteen."""
    entity = _concept_class().model_validate({**_SAMPLE, **_LOADER_SUPPLIED})
    assert entity.model_extra is not None
    assert entity.model_extra["promoted_from"] == "knowledge/sources/local/terms.yaml"


def test_the_projection_still_allows_extras():
    """The mechanism the six undeclared-but-admitted fields depend on.

    If `concept` gains a typed subclass, this is the line that must be kept true --
    or those six fields need declaring on it.
    """
    assert _concept_class().model_config.get("extra") == "allow"


def test_schema_profile_is_the_only_narrowed_field():
    narrowed = {
        name for name, spec in _composed_properties().items() if spec is False
    }
    assert narrowed == {"schema_profile"}
