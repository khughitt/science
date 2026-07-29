"""Schema closure: ONE declaration, and the surfaces that must agree with it.

`EntityKind.schema_closed` answers "does this kind validate through a composed profile with
`unevaluatedProperties: false`?" `PROJECT_MIXIN_NAMES` DERIVES from it, so asserting the two agree
would be the identity function. Every gate here therefore compares the declaration against an
INDEPENDENTLY HAND-AUTHORED artifact -- a generation row, a file on disk, a descriptor field --
each of which can genuinely disagree.
"""

from __future__ import annotations

import json
from importlib.resources import files

import pytest
from pydantic import ValidationError

from science_model.entity_schema.profile import (
    COMMONS_MIXIN_NAMES,
    PROJECT_MIXIN_NAMES,
    _MIXIN_VERSION_BY_GENERATION,
)
from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE
from science_model.profiles.schema import EntityKind, ProfileManifest

SHIPPED_KINDS: tuple[EntityKind, ...] = (*CORE_PROFILE.entity_kinds, *LOCAL_PROFILE.entity_kinds)


def test_every_shipped_kind_declares_schema_closed() -> None:
    # `model_fields_set` -- NOT the value. The False default is what keeps project-authored
    # manifest kinds inert, which means a shipped kind that merely forgot to declare would
    # otherwise be indistinguishable from one deliberately ruled open. Presence is the only
    # thing separating them.
    undeclared = sorted(k.name for k in SHIPPED_KINDS if "schema_closed" not in k.model_fields_set)
    assert not undeclared, f"shipped kinds not declaring schema_closed: {undeclared}"


def test_the_shipped_population_is_53() -> None:
    # Pins the population the other gates range over. A kind added without a ruling fails here
    # first, with a clearer message than a downstream equality.
    assert len(SHIPPED_KINDS) == 53


def test_the_armed_set_is_exactly_the_kinds_whose_slices_have_landed() -> None:
    # One entry per COMPLETED slice, and the list is hand-written so a kind cannot join by
    # accident: `PROJECT_MIXIN_NAMES` derives from `schema_closed`, so an equality against a
    # derived set would be the identity function. Growing this line without the seven-step
    # slice behind it is the partial release design 4.0 prohibits.
    #
    #   hypothesis -- D5
    #   concept    -- 2026-07-28, docs/plans/2026-07-28-schema-closure-concept-slice-inventory.md
    #   method     -- 2026-07-29, docs/plans/2026-07-29-schema-closure-method-slice-inventory.md
    #
    # Remaining tranche kinds, in order: search, observation, finding.
    assert PROJECT_MIXIN_NAMES == frozenset({"hypothesis", "concept", "method"})


_MINIMAL_EXTERNAL = {
    "name": "project-local",
    "imports": [],
    "relation_kinds": [],
    "strictness": "typed-extension",
}


def _external(kind: dict) -> dict:
    return {**_MINIMAL_EXTERNAL, "entity_kinds": [kind]}


_BASE_KIND = {
    "name": "widget",
    "canonical_prefix": "widget",
    "layer": "local",
    "description": "a project-local kind",
}


def test_an_external_manifest_may_NOT_author_schema_closed() -> None:
    # REJECTED, not ignored. A project cannot install a packaged type mixin, so honouring this
    # would be a claim the toolkit cannot make true -- and silently ignoring it is exactly the
    # fail-silent this programme abolishes.
    with pytest.raises(ValidationError, match="schema_closed"):
        ProfileManifest.model_validate(_external({**_BASE_KIND, "schema_closed": True}))


def test_an_external_manifest_may_not_author_schema_closed_FALSE_either() -> None:
    # Even the inert value is refused: accepting `false` would teach authors the key is theirs to
    # set, and the next edit flips it.
    with pytest.raises(ValidationError, match="schema_closed"):
        ProfileManifest.model_validate(_external({**_BASE_KIND, "schema_closed": False}))


def test_an_external_manifest_without_the_field_still_loads() -> None:
    manifest = ProfileManifest.model_validate(_external(dict(_BASE_KIND)))
    assert manifest.entity_kinds[0].schema_closed is False
    assert "schema_closed" not in manifest.entity_kinds[0].model_fields_set


def test_the_packaged_profiles_are_UNAFFECTED_by_the_rejection() -> None:
    # The packaged profiles construct EntityKind instances directly rather than validating raw
    # mappings, which is what makes one before-validator able to serve both external loaders
    # without touching the 53 shipped declarations. If this ever fails, the rejection has become
    # over-broad and the 53 explicit declarations are what it will reject.
    assert any(k.schema_closed for k in SHIPPED_KINDS)


def test_GATE_1_every_generation_row_matches_the_closed_declaration() -> None:
    # Commons mixins (dataset/paper/theme/topic) appear in every row but stay OPEN and pin base
    # 1.0, so they must not force schema_closed=True. Exact equality gives both directions: a
    # closed kind missing from a row fails, and a project mixin in a row with no closed
    # declaration fails. A kind closed in gen 2 but absent from gen 3 would raise
    # ProfileParseError at load for every gen-3 project -- a real failure this catches.
    declared = {k.name for k in SHIPPED_KINDS if k.schema_closed}
    for generation, row in _MIXIN_VERSION_BY_GENERATION.items():
        project_entries = set(row) - COMMONS_MIXIN_NAMES
        assert project_entries == declared, (
            f"generation {generation}: in the row but not declared closed: "
            f"{sorted(project_entries - declared)}; declared closed but missing from the row: "
            f"{sorted(declared - project_entries)}"
        )


def test_GATE_1_commons_kinds_are_represented_in_every_generation_row() -> None:
    # The standing assertion that keeps gate 1's commons EXCLUSION from quietly becoming a hole:
    # if a commons kind vanished from a row, the exclusion above would silently stop covering it.
    for generation, row in _MIXIN_VERSION_BY_GENERATION.items():
        missing = COMMONS_MIXIN_NAMES - set(row)
        assert not missing, f"generation {generation} omits commons kinds: {sorted(missing)}"


def _packaged_schema_names() -> set[str]:
    return {p.name for p in files("science_model.schemas").iterdir() if p.name.endswith(".json")}


def test_GATE_2_every_ARMED_component_resolves_to_a_packaged_file() -> None:
    # Deliberately NOT biconditional. Schema files are versioned artifacts and a dormant
    # historical or staged version may legitimately sit on disk -- four do today
    # (dataset-1.0, paper-1.0, theme-1.0, topic-1.0), armed by no row. A raw mixin-*.json scan
    # used as the reverse authority would have failed on day one.
    available = _packaged_schema_names()
    for generation, row in _MIXIN_VERSION_BY_GENERATION.items():
        for kind, version in row.items():
            expected = f"mixin-{kind}-{version}.json"
            assert expected in available, (
                f"generation {generation} arms {kind}/{version} but {expected} is not packaged"
            )


def test_GATE_2_every_armed_project_mixin_pins_its_own_kind() -> None:
    # The packaged mixin's `const` is the hand-authored artifact here. base-2.0 constrains `kind`
    # to a SHAPE only ("^[a-z][a-z0-9-]*$", with a $comment saying the mixin's const pins the
    # exact kind), so the const is the sole thing tying a composed schema to the kind it claims
    # to be. Copying mixin-hypothesis-1.0.json to mixin-<newkind>-1.0.json and forgetting to
    # change the const yields a schema that silently validates every record as a hypothesis --
    # the exact slice-author error, and one nothing else catches.
    #
    # Only files that EXIST are checked; a missing packaged file is the previous gate's finding,
    # and duplicating it here would report one defect as two.
    available = _packaged_schema_names()
    for generation, row in _MIXIN_VERSION_BY_GENERATION.items():
        for kind in set(row) - COMMONS_MIXIN_NAMES:
            name = f"mixin-{kind}-{row[kind]}.json"
            if name not in available:
                continue
            schema = json.loads(files("science_model.schemas").joinpath(name).read_text())
            assert schema.get("properties", {}).get("kind") == {"const": kind}, (
                f"generation {generation}: {name} does not pin kind to {kind!r}"
            )


def test_GATE_4_a_closed_kind_declares_entity_class_and_home() -> None:
    # An IMPLICATION, not an equality: many deliberately open kinds already declare both. A kind
    # with no `home` cannot be located in order to be validated.
    for kind in SHIPPED_KINDS:
        if not kind.schema_closed:
            continue
        assert kind.entity_class is not None, f"{kind.name} is closed but declares no entity_class"
        assert kind.home is not None, f"{kind.name} is closed but declares no home"
