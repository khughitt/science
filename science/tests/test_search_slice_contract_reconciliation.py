"""Step 5 of the search slice: reconcile the schema against the Pydantic projection.

The contract is "the SCHEMA refuses what it does not know, the PROJECTION preserves
what it admitted". This module checks that in the direction where a violation is a
defect: **every field the composed schema admits must survive projection.**

The other direction is not checked, and deliberately so. `search` has no typed
subclass -- `CORE_KIND_MODELS` has no entry, so it projects onto the generic
`ProjectEntity`, whose fields are shared with 29 other untyped kinds. A field
`ProjectEntity` declares that the search schema never admits (`taxon`, `datapackage`,
`benchmark`) is unreachable for this kind: dead weight in a shared model, not an
unvouched field. See "Untyped Kinds" in the slice procedure.

Five admitted fields are declared by no model field and survive on `extra="allow"`:
`contributors`, `licenses`, `sources`, `tags` and `version`. **No search record carries
any of them today**, which is the difference from the concept slice -- there,
`promoted_from` had 132 live records and the preservation was load-bearing immediately.
Here it is latent.

That preservation is a RULING, not an accident. `Entity` sets
`model_config = ConfigDict(extra="allow")` (entities.py:325) and its docstring cites
D3.3: *"Projections MUST preserve schema-valid extension fields. Never return to
`extra='ignore'` -- that is the original defect."* `ProjectEntity` inherits it.

So the risk these tests guard is narrower than "a subclass forgets": it is a subclass
that explicitly overrides `model_config`, which D3.3 forbids. Mutating `Entity` to
`extra="ignore"` turns ten assertions here red, which is what makes the ruling enforced
rather than merely written down.

This file runs while the mixin is DORMANT: it reads the packaged schema JSON and the
registry's resolved class directly, neither of which needs `search` armed. The step-5
DECLARATIONS -- the `UNHELD` manifest entries, `VALUE_RECONCILED_KINDS`, and the value
battery -- cannot land here; three guards refuse an entry for a `(generation, kind)` the
profile table does not yet have. They land in the step-7 commit.
"""

from __future__ import annotations

import json
from importlib.resources import files

import pytest

from science_tool.graph.entity_registry import EntityRegistry

_BASE = "science-entity-base-2.0.json"
_MIXIN = "mixin-search-1.0.json"


def _composed_properties() -> dict[str, object]:
    base = json.loads(files("science_model.schemas").joinpath(_BASE).read_text())
    mixin = json.loads(files("science_model.schemas").joinpath(_MIXIN).read_text())
    return {**base["properties"], **mixin["properties"]}


def _admitted() -> set[str]:
    return {name for name, spec in _composed_properties().items() if spec is not False}


def _search_class():
    return EntityRegistry.with_core_types().resolve_class("search")


# Values that satisfy each admitted field's declared type. Hand-written rather than
# generated from the schema: a generator would derive the input from the same document
# it is meant to be testing.
_SAMPLE: dict[str, object] = {
    "id": "search:0001-bulk-sc-integration-methods",
    "kind": "search",
    "title": "Methods for integrating single-cell and bulk RNA-seq data",
    "status": "active",
    "created": "2026-04-01",
    "updated": "2026-04-01",
    "profile": "local",
    "related": ["task:t021", "discussion:0008-sc-bulk-integration"],
    "source_refs": ["paper:survey-attractor-topology-methods"],
    "ontology_terms": ["MONDO:0005015"],
    "description": "A recorded literature search.",
    "tags": ["literature"],
    "version": "1",
    "contributors": ["kh"],
    "licenses": ["CC0-1.0"],
    "sources": ["knowledge/sources/local/entities.yaml"],
    "same_as": ["search:0002-existing-mm-meta-analyses"],
    "dataset_usage": [],
}

# What the loader supplies; `ProjectEntity` requires these but no author writes them.
_LOADER_SUPPLIED: dict[str, object] = {
    "project": "mm30",
    "content_preview": "",
    "file_path": "entities/searches/0001-bulk-sc-integration-methods.md",
}

# Admitted by the composed schema, declared by NO model field. Frozen deliberately: a
# field joining this set is a new gap and must be reconciled, and one leaving it is a
# model change that wants noticing. Derived once and pinned rather than recomputed in
# the assertion, which would compare the code against itself.
_UNDECLARED = {"contributors", "licenses", "sources", "tags", "version"}


def test_the_sample_covers_every_admitted_field():
    """Guards the guard: an admitted field with no sample would be silently unchecked."""
    assert _admitted() - set(_SAMPLE) == set()


@pytest.mark.parametrize("field", sorted(_admitted()))
def test_every_admitted_field_survives_projection(field):
    entity = _search_class().model_validate({**_SAMPLE, **_LOADER_SUPPLIED})
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
    """The latent case, asserted per field so a regression names itself.

    No search record carries any of these today -- unlike the concept slice, where
    `promoted_from` had 132. That makes this the cheap moment to pin the behaviour:
    there is no corpus pressure to notice it later.
    """
    entity = _search_class().model_validate({**_SAMPLE, **_LOADER_SUPPLIED})
    assert entity.model_extra is not None
    assert entity.model_extra[field] == _SAMPLE[field]


def test_the_projection_still_allows_extras():
    """The mechanism the five undeclared-but-admitted fields depend on.

    Inherited from `Entity` (entities.py:325), where D3.3 rules it may never revert to
    `extra="ignore"`. If `search` gains a typed subclass, this is the line that must be
    kept true -- or those five fields need declaring on it.
    """
    assert _search_class().model_config.get("extra") == "allow"


def test_schema_profile_is_the_only_narrowed_field():
    narrowed = {name for name, spec in _composed_properties().items() if spec is False}
    assert narrowed == {"schema_profile"}


def test_the_retired_task_keys_are_admitted_by_neither_authority():
    """The step-3 ruling, checked on both sides rather than only in the schema.

    The mixin omits `task`/`task_ref`, and `ProjectEntity` never declared them either --
    so before closure they were preserved as pydantic extras and read by nothing, which
    is precisely the "preserved unvouched" state this tranche exists to end.
    """
    from science_model.entities import ProjectEntity

    assert not ({"task", "task_ref"} & _admitted())
    assert not ({"task", "task_ref"} & set(ProjectEntity.model_fields))
