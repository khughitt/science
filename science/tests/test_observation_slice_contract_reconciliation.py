"""Step 5 of the observation slice: reconcile the schema against the Pydantic projection.

The contract is "the SCHEMA refuses what it does not know, the PROJECTION preserves
what it admitted". This module checks that in the direction where a violation is a
defect: **every field the composed schema admits must survive projection.**

The other direction is not checked, and deliberately so. `observation` has no typed
subclass -- `CORE_KIND_MODELS` has no entry, so it projects onto the generic
`ProjectEntity`, whose 70 fields are shared with 29 other untyped kinds. A field
`ProjectEntity` declares that the observation schema never admits (58 of them) is
unreachable for this kind: dead weight in a shared model, not an unvouched field. See
"Untyped Kinds" in the slice procedure.

Six admitted fields are declared by no model field and survive on `extra="allow"`, and
they split two ways -- which is the difference from the `search` slice, where all five
were latent:

- `promoted_from` is LOAD-BEARING NOW: 14 of the 21 authored records carry it, so
  preservation is exercised by the corpus the day this arms.
- `contributors`, `licenses`, `sources`, `tags` and `version` are latent: no observation
  record carries any of them.

That preservation is a RULING, not an accident. `Entity` sets
`model_config = ConfigDict(extra="allow")` (entities.py:325) and its docstring cites
D3.3: *"Projections MUST preserve schema-valid extension fields. Never return to
`extra='ignore'` -- that is the original defect."* `ProjectEntity` inherits it.

So the risk these tests guard is narrower than "a subclass forgets": it is a subclass
that explicitly overrides `model_config`, which D3.3 forbids.

This file runs while the mixin is DORMANT: it reads the packaged schema JSON and the
registry's resolved class directly, neither of which needs `observation` armed. The step-5
DECLARATIONS -- the `UNHELD` manifest entries, `VALUE_RECONCILED_KINDS`, and the value
battery -- cannot land here; three guards refuse an entry for a `(generation, kind)` the
profile table does not yet have. They land in the step-7 commit.
"""

from __future__ import annotations

import json
from importlib.resources import files

import pytest

from science_tool.graph.entity_registry import CORE_KIND_MODELS, EntityRegistry

_BASE = "science-entity-base-2.0.json"
_MIXIN = "mixin-observation-1.0.json"


def _composed_properties() -> dict[str, object]:
    base = json.loads(files("science_model.schemas").joinpath(_BASE).read_text())
    mixin = json.loads(files("science_model.schemas").joinpath(_MIXIN).read_text())
    return {**base["properties"], **mixin["properties"]}


def _admitted() -> set[str]:
    return {name for name, spec in _composed_properties().items() if spec is not False}


def _observation_class():
    return EntityRegistry.with_core_types().resolve_class("observation")


# Values that satisfy each admitted field's declared type. Hand-written rather than
# generated from the schema: a generator would derive the input from the same document
# it is meant to be testing.
_SAMPLE: dict[str, object] = {
    "id": "observation:swan-stage-cardiometabolic-shift",
    "kind": "observation",
    "title": "Natural postmenopause shifts lipids net of chronological age (SWAN)",
    "status": "active",
    "created": "2026-04-01",
    "updated": "2026-04-01",
    "related": ["hypothesis:0002-rhythm-confounding-of-biomarkers"],
    "source_refs": ["interpretation:0001-swan-stage-vs-age-deconvolution", "dataset:swan"],
    "promoted_from": "doc/observations/observations.yaml",
    "ontology_terms": ["MONDO:0005015"],
    "description": "A concrete empirical fact anchored to specific data.",
    "tags": ["swan"],
    "version": "1",
    "contributors": ["kh"],
    "licenses": ["CC0-1.0"],
    "sources": ["doc/observations/observations.yaml"],
    "same_as": ["observation:swan-age-slope-deconvolution"],
    "dataset_usage": [],
}

# What the loader supplies; `ProjectEntity` requires these but no author writes them.
_LOADER_SUPPLIED: dict[str, object] = {
    "project": "cycles",
    "content_preview": "",
    "file_path": "entities/observations/swan-stage-cardiometabolic-shift.md",
}

# Admitted by the composed schema, declared by NO model field. Frozen deliberately: a
# field joining this set is a new gap and must be reconciled, and one leaving it is a
# model change that wants noticing. Derived once and pinned rather than recomputed in
# the assertion, which would compare the code against itself.
#
# SIX, not the `search` slice's five. `promoted_from` is the extra one, because this mixin
# admits it and that one does not -- the count is derived per kind, never copied. The
# `search` slice recorded the same lesson from the other side: its UNHELD manifest needed
# five entries where `concept` and `method` needed six.
_UNDECLARED = {"contributors", "licenses", "promoted_from", "sources", "tags", "version"}

# The subset a real record exercises today. `promoted_from` alone: 14 of 21.
_LIVE_UNDECLARED = {"promoted_from"}


def test_the_sample_covers_every_admitted_field():
    """Guards the guard: an admitted field with no sample would be silently unchecked."""
    assert _admitted() - set(_SAMPLE) == set()


@pytest.mark.parametrize("field", sorted(_admitted()))
def test_every_admitted_field_survives_projection(field):
    entity = _observation_class().model_validate({**_SAMPLE, **_LOADER_SUPPLIED})
    dumped = entity.model_dump()
    assert field in dumped, (
        f"the composed schema admits {field!r} and the projection dropped it"
    )


def test_the_undeclared_set_is_exactly_what_the_model_does_not_declare():
    """Pins the gap direction as a measurement, in both directions.

    A field added to the mixin that the model does not declare fails here rather than
    silently relying on `extra="allow"`; and a model that starts declaring one of these
    fails too, which is the signal to drop it from the manifest.
    """
    from science_model.entities import ProjectEntity

    assert _admitted() - set(ProjectEntity.model_fields) == _UNDECLARED


@pytest.mark.parametrize("field", sorted(_UNDECLARED))
def test_each_undeclared_field_is_preserved_as_an_extra(field):
    entity = _observation_class().model_validate({**_SAMPLE, **_LOADER_SUPPLIED})
    assert entity.model_extra is not None
    assert entity.model_extra[field] == _SAMPLE[field]


def test_the_live_undeclared_field_is_the_one_the_corpus_exercises():
    """Which of the six preservations is load-bearing TODAY, pinned as a fact.

    14 of 21 records carry `promoted_from` and none carries any of the other five. That
    matters for reading a failure: a regression in `promoted_from` preservation breaks the
    real corpus on the day it arms, while a regression in the other five is latent and
    would surface only when someone first authors one.
    """
    assert _LIVE_UNDECLARED < _UNDECLARED
    entity = _observation_class().model_validate({**_SAMPLE, **_LOADER_SUPPLIED})
    assert entity.model_extra is not None
    assert entity.model_extra["promoted_from"] == "doc/observations/observations.yaml"


def test_the_projection_still_allows_extras():
    """The mechanism all six undeclared-but-admitted fields depend on.

    Inherited from `Entity` (entities.py:325), where D3.3 rules it may never revert to
    `extra="ignore"`. If `observation` gains a typed subclass, this is the line that must
    be kept true -- or those six fields need declaring on it.
    """
    assert _observation_class().model_config.get("extra") == "allow"


def test_observation_really_is_untyped():
    """Why step 5 is the one-directional variant for this kind.

    Asserted rather than assumed: if `observation` gains a `CORE_KIND_MODELS` entry, the
    surplus direction stops being "dead weight in a shared model" and becomes a real
    reconciliation obligation, and this file's whole premise needs revisiting.
    """
    assert "observation" not in CORE_KIND_MODELS
    from science_model.entities import ProjectEntity

    assert _observation_class() is ProjectEntity


def test_schema_profile_is_the_only_narrowed_field():
    narrowed = {name for name, spec in _composed_properties().items() if spec is False}
    assert narrowed == {"schema_profile"}


def test_the_omitted_writer_keys_are_admitted_by_neither_authority():
    """The slice's rulings, checked on both sides rather than only in the schema.

    `consolidated_into` and `superseded_by` are omitted by the mixin, and `ProjectEntity`
    never declared either -- so before closure they would have been preserved as pydantic
    extras and read by nothing, which is precisely the "preserved unvouched" state this
    tranche exists to end. `profile` is the third omission but is NOT checked here: it is a
    real `ProjectEntity` field, so it fails the schema half and passes the model half, and
    its ruling lives in the mixin's probes.
    """
    from science_model.entities import ProjectEntity

    omitted = {"consolidated_into", "superseded_by"}
    assert not (omitted & _admitted())
    assert not (omitted & set(ProjectEntity.model_fields))
