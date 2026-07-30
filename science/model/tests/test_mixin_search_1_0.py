"""Probes for the ARMED `mixin-search-1.0` schema.

Authored dormant in step 2 and armed in step 7. Both generation rows select it and
`schema_closed=True` on the descriptor, so this is now what the toolkit loads.

Every strict probe composes the candidate profile through the REAL
`EntityValidator._compose` (via `validate_as`). Hand-rolling
`{"allOf": [...], "unevaluatedProperties": False}` here instead would certify this
test file's idea of composition rather than the toolkit's.

Arming a kind flips TWO independent lookups, and the fixture patches both because
step 7 satisfied both from ONE declaration (`schema_closed=True`), so the pair cannot
drift apart. The fixture is now redundant with production for this kind and is kept
because the value/mutation probes read more clearly when the arming is explicit:

- `validator.py:135` gates `unevaluatedProperties: false` on `PROJECT_MIXIN_NAMES`;
- `loader.py:92` gates the `mixin-` filename prefix on `TYPE_MIXIN_NAMES`, so an
  unarmed name resolves to `extension-search-1.0.json` and is not found at all.

Both are patched in the CONSUMING module's namespace, not in `profile`: each does
`from ...profile import <NAME>`, which binds a new name at import time, so rebinding
the source module would not be seen.
"""

import json
from pathlib import Path

import pytest
from science_model.entity_schema import loader as loader_module
from science_model.entity_schema import validator as validator_module
from science_model.entity_schema.profile import (
    BASE_NAME,
    PROJECT_MIXIN_NAMES,
    TYPE_MIXIN_NAMES,
    ProfileComponent,
    ProfileString,
    default_profile_for_kind,
)
from science_model.entity_schema.validator import EntityValidationError, EntityValidator

SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"
TEMPLATES = Path(__file__).resolve().parents[1] / "src" / "science_model" / "templates"

CANDIDATE = ProfileString(
    base=ProfileComponent(BASE_NAME, "2.0"),
    mixin=ProfileComponent("search", "1.0"),
    extensions=(),
)


def _mixin() -> dict:
    return json.loads((SCHEMAS / "mixin-search-1.0.json").read_text())


def _record(**overrides) -> dict:
    """A minimal record every one of the 36 authored searches satisfies."""
    record = {
        "id": "search:0001-bulk-sc-integration-methods",
        "kind": "search",
        "title": "Methods for integrating single-cell and bulk RNA-seq data",
        "status": "active",
        "created": "2026-04-01",
        "updated": "2026-04-01",
    }
    record.update(overrides)
    return record


@pytest.fixture
def strict(monkeypatch) -> EntityValidator:
    """An EntityValidator that composes `search` STRICTLY, as production now does."""
    monkeypatch.setattr(validator_module, "PROJECT_MIXIN_NAMES", PROJECT_MIXIN_NAMES | {"search"})
    monkeypatch.setattr(loader_module, "TYPE_MIXIN_NAMES", TYPE_MIXIN_NAMES | {"search"})
    return EntityValidator()


def _refuses(validator: EntityValidator, record: dict) -> str:
    with pytest.raises(EntityValidationError) as caught:
        validator.validate_as(record, CANDIDATE)
    return str(caught.value)


# --- armed: both lookups flipped, from one declaration ---------------------------
#
# These four were written INVERTED while dormant and flipped in the same commit that
# added the generation rows and set `schema_closed=True`. That is what makes the arming
# commit self-certifying rather than merely plausible.


def test_search_is_armed():
    assert "search" in PROJECT_MIXIN_NAMES
    assert "search" in TYPE_MIXIN_NAMES


@pytest.mark.parametrize("generation", [2, 3])
def test_both_generation_rows_select_the_search_mixin(generation):
    """Both rows, at the same version, and neither detail is incidental.

    natural-systems is pinned to generation 2 and mm30 to generation 3, so arming one
    row would split one kind's contract across the corpus -- and both projects hold
    `search` records. `sources.py:1704` calls `default_profile_for_kind(entity.kind)`
    with no generation argument and always resolves row 2, so the two rows agreeing is
    what keeps that call site consistent with the projects it resolves for.
    """
    profile = default_profile_for_kind("search", generation=generation)
    assert profile.render() == "science-entity-base/2.0+search/1.0"


def test_the_mixin_is_now_reachable_as_a_mixin():
    """`loader.py:92` derives the filename prefix from `TYPE_MIXIN_NAMES`.

    While dormant this raised for `extension-search-1.0.json`: the file on disk was not
    lax, it was unreachable. That distinction is the one the slice procedure insists on --
    an unarmed mixin is not a weak mixin.
    """
    EntityValidator().validate_as(_record(), CANDIDATE)


def test_composition_now_closes():
    """The defect this slice closes, asserted against the real composer.

    While dormant this test patched ONLY the loader and asserted that `shadow_key` SAILED
    THROUGH -- isolating the second lookup to demonstrate what "preserved unvouched"
    meant for this kind. Now both lookups derive from `schema_closed=True` and the same
    record is refused.
    """
    with pytest.raises(EntityValidationError) as caught:
        EntityValidator().validate_as(_record(shadow_key="unvouched"), CANDIDATE)
    assert "shadow_key" in str(caught.value)


# --- value probes: the measured corpus validates ---------------------------------


def test_minimal_authored_record_validates(strict):
    strict.validate_as(_record(), CANDIDATE)


def test_record_with_every_observed_non_base_field_validates(strict):
    strict.validate_as(
        _record(
            profile="local",
            related=["task:t021", "question:0015-topological-structure"],
            source_refs=["paper:survey-attractor-topology-methods"],
        ),
        CANDIDATE,
    )


def test_the_single_ontology_terms_record_validates(strict):
    """Exactly one of the 36 carries it, and base 2.0 -- not this mixin -- admits it.

    Asserted here anyway: if a future base version dropped it, this kind's corpus would
    break and no probe in this file would otherwise notice.
    """
    strict.validate_as(_record(ontology_terms=[]), CANDIDATE)


@pytest.mark.parametrize(
    "value",
    ["active", "complete", "retired", "archived", "proposed"],
)
def test_the_status_shape_is_admitted_without_the_vocabulary(strict, value):
    """The standing ruling, asserted where a uniform corpus would otherwise hide it.

    All 36 records are `active`, so every value probe over the corpus passes whether or
    not the schema enum-locks the field -- exactly how `mixin-concept-1.0`'s premature
    enum survived its own certification. The first four values are the descriptor's
    vocabulary (profiles/core.py:569); `proposed` is deliberately outside it, because
    `search` is not in `_CERTIFIED_KINDS` and an uncertified vocabulary may not refuse a
    record at load.
    """
    strict.validate_as(_record(status=value), CANDIDATE)


# --- mutation probes: what the closed schema must refuse -------------------------


def test_undeclared_key_is_refused(strict):
    assert "shadow_key" in _refuses(strict, _record(shadow_key="unvouched"))


def test_foreign_kind_is_refused(strict):
    _refuses(strict, _record(kind="concept"))


def test_foreign_id_prefix_is_refused(strict):
    """`kind` alone would pass; the id would name a different entity."""
    _refuses(strict, _record(id="method:0001-bulk-sc-integration-methods"))


def test_a_non_string_status_is_refused(strict):
    """Dropping the vocabulary does not drop the shape."""
    _refuses(strict, _record(status=42))


def test_missing_status_is_refused(strict):
    record = _record()
    del record["status"]
    _refuses(strict, record)


def test_authored_schema_profile_is_refused(strict):
    """The narrowing: `profile` is the authored field, `schema_profile` its derived one."""
    _refuses(strict, _record(schema_profile=f"{BASE_NAME}/2.0+search/1.0"))


@pytest.mark.parametrize("key", ["task", "task_ref"])
def test_the_retired_task_keys_are_refused(strict, key):
    """The slice's ruling, and the teeth behind the corpus migration.

    Two projects independently invented these for one association -- `task:` in
    cancer/multiple-myeloma (5 records), `task_ref:` in natural-systems (2). NEITHER is
    read by any production code: `consolidation_candidates.py:92` `_task_refs()` reads
    `related` and selects `task:`-prefixed items, and its local variable is merely NAMED
    `task_ref`. The association is expressed in `related` instead, which is the only
    spelling production sees. These refusals are what make the migration required rather
    than advisory.
    """
    _refuses(strict, _record(**{key: "task:t021"}))


def test_scalar_related_is_refused(strict):
    _refuses(strict, _record(related="task:t021"))


def test_non_string_related_item_is_refused(strict):
    _refuses(strict, _record(related=[3]))


def test_non_string_source_refs_item_is_refused(strict):
    _refuses(strict, _record(source_refs=[3]))


# --- production surfaces ----------------------------------------------------------


def test_no_packaged_template_exists_for_search():
    """`search` has NO template, unlike both completed slices.

    Asserted rather than assumed, and in the direction that catches the change: adding
    `templates/search.md` without inventorying its emitted field set turns this red,
    which is exactly when the `method` slice's `omit: true` lesson would start applying
    to this kind.
    """
    assert not (TEMPLATES / "search.md").exists()
    assert (TEMPLATES / "observation.md").exists(), (
        "control: the templates directory is the right one and does hold sibling kinds"
    )


# --- the mixin's own declaration -------------------------------------------------


def test_mixin_pins_its_own_kind():
    """Gate 2's requirement, asserted here too so the file is self-certifying."""
    assert _mixin()["properties"]["kind"] == {"const": "search"}


def test_status_declares_no_enum():
    status = _mixin()["properties"]["status"]
    assert status["type"] == "string"
    assert "enum" not in status
    # The key set too, so a `const` or `pattern` smuggling the vocabulary back in is
    # caught by the same test that catches `enum`.
    assert set(status) == {"type", "$comment"}


def test_mixin_declares_exactly_the_frozen_field_set():
    """The step-1 inventory, as an assertion.

    A field added to the mixin without going through the inventory fails here -- which
    is the point. `schema_profile` is present as `false`, the reserved narrowing.
    `promoted_from` is ABSENT and that is a decision: nothing promotes into `search`.
    """
    assert set(_mixin()["properties"]) == {
        "id",
        "kind",
        "status",
        "profile",
        "related",
        "source_refs",
        "schema_profile",
    }
