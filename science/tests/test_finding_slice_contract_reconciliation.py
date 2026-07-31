"""Step 5 of the finding slice: reconcile the schema against the Pydantic projection.

The contract is "the SCHEMA refuses what it does not know, the PROJECTION preserves
what it admitted". This module checks that in the direction where a violation is a
defect: **every field the composed schema admits must survive projection.**

The other direction is not checked, and deliberately so. `finding` has no typed subclass
-- `CORE_KIND_MODELS` has no entry, so it projects onto the generic `ProjectEntity`, whose
70 fields are shared with 29 other untyped kinds. A field `ProjectEntity` declares that the
finding schema never admits is unreachable for this kind: dead weight in a shared model,
not an unvouched field. See "Untyped Kinds" in the slice procedure.

**ELEVEN admitted fields are declared by no model field**, nearly double `observation`'s
six and more than double `search`'s five. The count is derived per kind, never copied --
this mixin admits five keys no earlier tranche mixin did (`mode`, `input`, `propositions`,
`observations`, `superseded_by`), and each one widens the gap by construction. They split
two ways:

- LOAD-BEARING NOW, exercised by the corpus the day this arms: `promoted_from` (26 of 52),
  `propositions` (25), `observations` (25), `mode` (23), `input` (22).
- Latent, carried by no finding anywhere: `contributors`, `licenses`, `sources`, `tags`,
  `version`, and `superseded_by`.

`superseded_by` being latent is the point of admitting it. `finding` is `supersedable=True`
and `mark_superseded` stamps the key into frontmatter, so the field is zero-occurrence and
one CLI call away -- and `graph/materialize.py:185` reads it. A model that dropped it on
projection would lose lineage the moment the writer ran.

That preservation is a RULING, not an accident. `Entity` sets
`model_config = ConfigDict(extra="allow")` (entities.py:325) and its docstring cites D3.3:
*"Projections MUST preserve schema-valid extension fields. Never return to
`extra='ignore'` -- that is the original defect."* `ProjectEntity` inherits it. So the risk
these tests guard is narrower than "a subclass forgets": it is a subclass that explicitly
overrides `model_config`, which D3.3 forbids.

This file runs while the mixin is DORMANT: it reads the packaged schema JSON and the
registry's resolved class directly, neither of which needs `finding` armed. The step-5
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
_MIXIN = "mixin-finding-1.0.json"


def _composed_properties() -> dict[str, object]:
    base = json.loads(files("science_model.schemas").joinpath(_BASE).read_text())
    mixin = json.loads(files("science_model.schemas").joinpath(_MIXIN).read_text())
    return {**base["properties"], **mixin["properties"]}


def _admitted() -> set[str]:
    return {name for name, spec in _composed_properties().items() if spec is not False}


def _finding_class():
    return EntityRegistry.with_core_types().resolve_class("finding")


# Values that satisfy each admitted field's declared type. Hand-written rather than
# generated from the schema: a generator would derive the input from the same document it
# is meant to be testing.
_SAMPLE: dict[str, object] = {
    "id": "finding:0005-equiv-calibration-full",
    "kind": "finding",
    "title": "Full equivalence calibration calibrates 71/74 strata",
    "status": "active",
    "created": "2026-06-21",
    "updated": "2026-06-21",
    "profile": "project_specific",
    "file_path": "knowledge/sources/project_specific/finding.yaml",
    "related": ["hypothesis:0007-empirical-fidelity-alignment"],
    "source_refs": ["dataset:arxiv-formula-equivalence"],
    "aliases": ["f05"],
    "evidence_refs": ["limit-relation:asep__burgers-equation__a"],
    "propositions": ["proposition:concept-a-affects-concept-b"],
    "observations": ["observation:swan-stage-cardiometabolic-shift"],
    "mode": "empirical-measurement",
    "input": "data/processed/arxiv/catalog/catalog.parquet",
    "relations": [
        {"predicate": "sci:amends", "target": "finding:0016-curated-catalog"}
    ],
    "promoted_from": "knowledge/sources/local/entities.yaml",
    "superseded_by": "finding:0021-x",
    "ontology_terms": ["MONDO:0005015"],
    "description": "A unit of learned knowledge.",
    "tags": ["arxiv"],
    "version": "1",
    "contributors": ["kh"],
    "licenses": ["CC0-1.0"],
    "sources": ["knowledge/sources/local/entities.yaml"],
    "same_as": ["finding:0004-equiv-calibration-pilot"],
    "dataset_usage": [],
}

# What the loader supplies; `ProjectEntity` requires these but no author writes them.
_LOADER_SUPPLIED: dict[str, object] = {
    "project": "natural-systems",
    "content_preview": "",
}

# Admitted by the composed schema, declared by NO model field. Frozen deliberately: a field
# joining this set is a new gap that must be reconciled, and one leaving it is a model
# change that wants noticing. Derived once and pinned rather than recomputed in the
# assertion, which would compare the code against itself.
_UNDECLARED = {
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

# The subset a real record exercises today -- five of the eleven, where `observation` had
# one of six. This kind's gap is not merely wider, it is substantially LIVE.
_LIVE_UNDECLARED = {"promoted_from", "propositions", "observations", "mode", "input"}


def test_the_sample_covers_every_admitted_field():
    """Without this, a field added to the schema would silently escape the battery below."""
    assert set(_SAMPLE) == _admitted()


@pytest.mark.parametrize("field", sorted(_admitted()))
def test_every_admitted_field_survives_projection(field):
    entity = _finding_class().model_validate({**_SAMPLE, **_LOADER_SUPPLIED})
    dumped = entity.model_dump(mode="json")
    assert field in dumped, f"{field} was admitted by the schema and dropped by projection"


def test_the_undeclared_set_is_exactly_what_the_model_does_not_declare():
    """Two-directional, so a stale exemption fails as loudly as a new gap."""
    from science_model.entities import ProjectEntity

    assert _admitted() - set(ProjectEntity.model_fields) == _UNDECLARED


@pytest.mark.parametrize("field", sorted(_UNDECLARED))
def test_each_undeclared_field_is_preserved_as_an_extra(field):
    entity = _finding_class().model_validate({**_SAMPLE, **_LOADER_SUPPLIED})
    assert entity.model_dump(mode="json")[field] == _SAMPLE[field]


def test_the_live_undeclared_fields_are_the_ones_the_corpus_exercises():
    """Five of the eleven are carried by real records, so preservation is exercised on day
    one rather than being latent. Recorded because a latent gap and a live one are the same
    shape in the manifest and very different in consequence."""
    assert _LIVE_UNDECLARED < _UNDECLARED


def test_superseded_by_is_latent_but_one_cli_call_away():
    """The zero-occurrence field, and why its preservation is not theoretical.

    No finding authors it. `finding` is `supersedable=True`, `mark_superseded` stamps it
    into frontmatter, and `graph/materialize.py:185` reads it for live lineage. Latent
    today, load-bearing the first time anyone supersedes a finding.
    """
    assert "superseded_by" in _UNDECLARED
    assert "superseded_by" not in _LIVE_UNDECLARED


def test_finding_really_is_untyped():
    """The premise of this whole file. If `finding` ever gains a typed subclass, step 5
    reverts to the two-directional check as originally written."""
    assert "finding" not in CORE_KIND_MODELS
    from science_model.entities import ProjectEntity

    assert _finding_class() is ProjectEntity


def test_the_projection_still_allows_extras():
    """D3.3 directly: the preservation half of the contract is a config setting, and this
    is the one line whose change would silently break every assertion above."""
    assert _finding_class().model_config.get("extra") == "allow"


def test_schema_profile_is_the_only_narrowed_field():
    """`false` is reserved for a base-admitted field the kind deliberately narrows away.
    Everything else the mixin refuses is refused by OMISSION, per the procedure's rule
    against a 231-entry deny list."""
    narrowed = {name for name, spec in _composed_properties().items() if spec is False}
    assert narrowed == {"schema_profile"}


def test_the_omitted_writer_keys_are_admitted_by_neither_authority():
    """`consolidated_into` and a relation's `note`: both reachable from a writer, both
    refused. Asserted against both authorities so that admitting one later cannot pass
    quietly."""
    from science_model.entities import ProjectEntity

    assert "consolidated_into" not in _admitted()
    assert "consolidated_into" not in ProjectEntity.model_fields

    relation_def = json.loads(files("science_model.schemas").joinpath(_MIXIN).read_text())
    authored_relation = relation_def["$defs"]["authored_relation"]
    assert authored_relation["additionalProperties"] is False
    assert set(authored_relation["properties"]) == {"predicate", "target", "graph_layer"}
