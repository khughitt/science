"""Probes for the DORMANT `mixin-observation-1.0` schema.

Authored dormant in step 2 and armed in step 7. Until then no generation row selects
it and `schema_closed=False` on the descriptor, so this file is what the toolkit
*would* load, not what it loads.

Every strict probe composes the candidate profile through the REAL
`EntityValidator._compose` (via `validate_as`). Hand-rolling
`{"allOf": [...], "unevaluatedProperties": False}` here instead would certify this
test file's idea of composition rather than the toolkit's.

Arming a kind flips TWO independent lookups, and both must be patched to exercise the
armed behaviour ahead of arming:

- `validator.py:135` gates `unevaluatedProperties: false` on `PROJECT_MIXIN_NAMES`;
- `loader.py:92` gates the `mixin-` filename prefix on `TYPE_MIXIN_NAMES`, so an
  unarmed name resolves to `extension-observation-1.0.json` and is not found at all.
  An unarmed mixin is UNREACHABLE, not lax -- the distinction the slice procedure
  insists on.

Both are patched in the CONSUMING module's namespace, not in `profile`: each does
`from ...profile import <NAME>`, which binds a new name at import time, so rebinding
the source module would not be seen. Six modules bind `PROJECT_MIXIN_NAMES` by value
at import, which is also why patch-based simulation is never a substitute for step 7.

The four `dormant` tests below are written INVERTED and are flipped in the same commit
that adds the generation rows and sets `schema_closed=True`. That is what makes the
arming commit self-certifying rather than merely plausible.
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
    ProfileParseError,
    ProfileString,
    default_profile_for_kind,
)
from science_model.entity_schema.validator import EntityValidationError, EntityValidator

SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"
TEMPLATES = Path(__file__).resolve().parents[1] / "src" / "science_model" / "templates"

CANDIDATE = ProfileString(
    base=ProfileComponent(BASE_NAME, "2.0"),
    mixin=ProfileComponent("observation", "1.0"),
    extensions=(),
)


def _mixin() -> dict:
    return json.loads((SCHEMAS / "mixin-observation-1.0.json").read_text())


def _record(**overrides) -> dict:
    """A minimal record every one of the 21 authored observations satisfies."""
    record = {
        "id": "observation:swan-stage-cardiometabolic-shift",
        "kind": "observation",
        "title": "Natural postmenopause shifts lipids net of chronological age (SWAN)",
        "status": "active",
        "created": "2026-04-01",
        "updated": "2026-04-01",
    }
    record.update(overrides)
    return record


@pytest.fixture
def strict(monkeypatch) -> EntityValidator:
    """An EntityValidator that composes `observation` STRICTLY, as production will."""
    monkeypatch.setattr(
        validator_module, "PROJECT_MIXIN_NAMES", PROJECT_MIXIN_NAMES | {"observation"}
    )
    monkeypatch.setattr(loader_module, "TYPE_MIXIN_NAMES", TYPE_MIXIN_NAMES | {"observation"})
    return EntityValidator()


def _refuses(validator: EntityValidator, record: dict) -> str:
    with pytest.raises(EntityValidationError) as caught:
        validator.validate_as(record, CANDIDATE)
    return str(caught.value)


# --- dormant: neither lookup is flipped yet ---------------------------------------


def test_observation_is_not_yet_armed():
    assert "observation" not in PROJECT_MIXIN_NAMES
    assert "observation" not in TYPE_MIXIN_NAMES


@pytest.mark.parametrize("generation", [2, 3])
def test_no_generation_row_selects_the_observation_mixin(generation):
    """Both rows, because arming one would split one kind's contract across the corpus.

    That risk is theoretical for THIS kind and stated anyway: all 21 records live in a
    single project root pinned to generation 3, so no generation-2 project holds an
    `observation`. The rows still move together at step 7, because
    `sources.py` calls `default_profile_for_kind(entity.kind)` with no generation
    argument and always resolves row 2 -- a row-3-only arming would leave that call site
    resolving a profile the descriptor claims is closed.
    """
    with pytest.raises(ProfileParseError):
        default_profile_for_kind("observation", generation=generation)


def test_the_mixin_is_not_yet_reachable_as_a_mixin():
    """`loader.py:92` derives the filename prefix from `TYPE_MIXIN_NAMES`.

    While dormant this resolves to `extension-observation-1.0.json`: the file on disk is
    not lax, it is unreachable. Flipped at step 7.
    """
    with pytest.raises(Exception) as caught:
        EntityValidator().validate_as(_record(), CANDIDATE)
    assert "extension-observation-1.0" in str(caught.value)


def test_composition_does_not_yet_close():
    """The defect this slice closes, demonstrated for this kind.

    Only the LOADER is patched here, isolating the second lookup: the mixin is found,
    composition runs, and an undeclared key still sails through because
    `unevaluatedProperties: false` is gated on `PROJECT_MIXIN_NAMES`. This is what
    "preserved unvouched" means concretely. Flipped to a refusal at step 7.
    """
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(loader_module, "TYPE_MIXIN_NAMES", TYPE_MIXIN_NAMES | {"observation"})
        EntityValidator().validate_as(_record(shadow_key="unvouched"), CANDIDATE)


# --- value probes: the measured corpus validates ---------------------------------


def test_minimal_authored_record_validates(strict):
    strict.validate_as(_record(), CANDIDATE)


def test_record_with_every_observed_non_base_field_validates(strict):
    """All three non-base fields at once.

    `related` and `source_refs` are carried by 21 of 21; `promoted_from` by 14.
    """
    strict.validate_as(
        _record(
            related=["hypothesis:0002-rhythm-confounding-of-biomarkers"],
            source_refs=["interpretation:0001-swan-stage-vs-age-deconvolution", "dataset:swan"],
            promoted_from="doc/observations/observations.yaml",
        ),
        CANDIDATE,
    )


def test_the_retired_promotion_source_path_validates(strict):
    """All 14 `promoted_from` values are this one string, and the file NO LONGER EXISTS.

    `~/d/health/processes/cycles` commit 433ad02 deleted `doc/observations/observations.yaml`
    in the same commit that created the 14 owner files. That is correct provenance --
    `promoted_from` names where an entity CAME FROM, and it came from a file that was
    deliberately retired -- so the frozen oracle is a `minLength: 1` string with no
    existence check, and there must not be one.
    """
    strict.validate_as(_record(promoted_from="doc/observations/observations.yaml"), CANDIDATE)


@pytest.mark.parametrize("value", ["active", "retired", "archived", "proposed", "draft"])
def test_the_status_shape_is_admitted_without_the_vocabulary(strict, value):
    """The standing ruling, asserted where a uniform corpus would otherwise hide it.

    All 21 records are `active`, so every value probe over the corpus passes whether or
    not the schema enum-locks the field -- exactly how `mixin-concept-1.0`'s premature
    enum survived its own certification. The first three values are the descriptor's
    vocabulary (profiles/core.py:150); `proposed` and `draft` are deliberately outside
    it, because `observation` is not in `_CERTIFIED_KINDS` and an uncertified vocabulary
    may not refuse a record at load.

    This kind is the sharpest case in the tranche: with one project root owning every
    record, there is not even a second project whose divergence could expose an
    over-tight vocabulary the way `method`'s single `status: proposed` record did.
    """
    strict.validate_as(_record(status=value), CANDIDATE)


def test_base_admitted_fields_no_observation_record_carries_still_validate(strict):
    """Base 2.0's fields are admitted through composition, not through this mixin.

    No `observation` record carries any of these. Asserted anyway: if a future base
    version dropped one, this kind would lose it silently, and no corpus-derived probe
    would notice because the corpus never exercised it.
    """
    strict.validate_as(
        _record(description="A concrete empirical fact.", tags=["swan"], ontology_terms=[]),
        CANDIDATE,
    )


# --- mutation probes: what the closed schema must refuse -------------------------


def test_undeclared_key_is_refused(strict):
    assert "shadow_key" in _refuses(strict, _record(shadow_key="unvouched"))


def test_foreign_kind_is_refused(strict):
    _refuses(strict, _record(kind="finding"))


def test_foreign_id_prefix_is_refused(strict):
    """`kind` alone would pass; the id would name a different entity."""
    _refuses(strict, _record(id="finding:0001-swan-stage-cardiometabolic-shift"))


def test_a_non_string_status_is_refused(strict):
    """Dropping the vocabulary does not drop the shape."""
    _refuses(strict, _record(status=42))


def test_missing_status_is_refused(strict):
    record = _record()
    del record["status"]
    _refuses(strict, record)


def test_authored_schema_profile_is_refused(strict):
    """The narrowing base 2.0 itself prescribes for a project kind.

    Base 2.0's `schema_profile` `$comment` states the rule: it stays declared because
    commons records legitimately author it, and "a project kind's mixin sets this to
    `false`". `observation` is a project kind.
    """
    _refuses(strict, _record(schema_profile=f"{BASE_NAME}/2.0+observation/1.0"))


def test_an_empty_promoted_from_is_refused(strict):
    """`minLength: 1` is part of the frozen oracle, not decoration."""
    _refuses(strict, _record(promoted_from=""))


def test_profile_is_refused(strict):
    """The omission, with teeth -- and the one place slice 3's reasoning is corrected.

    `search` admits `profile` on the stated ground that the loader injects it. It does
    not: the `setdefault("profile", ...)` call is on the STRUCTURED-row path
    (`sources.py:1268`), and enrichment runs after `validate_against_schema` in any case,
    so nothing it adds can face the schema. Instrumenting the validator on a real gen-3
    load shows the validated key set is the authored frontmatter minus exactly
    `{canonical_id, content, file_path}`.

    So the field is authored or it is nothing -- and 0 of 21 observations author it, as
    do 0 of the 539 entity records in the only project that holds this kind. Omission is
    the procedure's default refusal.
    """
    assert "profile" in _refuses(strict, _record(profile="local"))


def test_consolidated_into_is_refused(strict):
    """The slice's ruling, and the teeth behind the `unarchive` fix.

    `consolidate.py:183` writes this key onto a member's frontmatter before relocating it
    to `entities/_archive/`, where nothing loads it. `unarchive_entities` was a bare
    `shutil.move`, so it restored the file to a LIVE, schema-validated path with the key
    still present -- failing the whole project load, not just the record. Verified
    end-to-end against armed `search` before the fix.

    The field is omitted rather than admitted because the frontmatter copy has no
    semantic reader: `entities.py:1004` and `big_picture/digests.py:77` both read
    `ArchiveRow.consolidated_into` from the archive index. Step 3 strips it on restore,
    so this refusal is the schema agreeing with the writer rather than fighting it.
    """
    assert "consolidated_into" in _refuses(
        strict, _record(status="archived", consolidated_into="synthesis:0001-d")
    )


def test_superseded_by_is_refused(strict):
    """Not an oversight -- the omission ENFORCES the descriptor.

    `observation` is `supersedable=False` (profiles/core.py:151), and
    `consolidation.py:641` derives the supersedes policy's `supported_kinds` from exactly
    that flag, so `mark_superseded` can never stamp an observation. Contrast
    `mixin-method-1.0`, which omits the field for a kind that IS supersedable -- a
    reachable defect filed as F7.
    """
    assert "superseded_by" in _refuses(
        strict, _record(status="retired", superseded_by="observation:other")
    )


def test_scalar_related_is_refused(strict):
    _refuses(strict, _record(related="hypothesis:0002-rhythm-confounding-of-biomarkers"))


def test_non_string_related_item_is_refused(strict):
    _refuses(strict, _record(related=[3]))


def test_non_string_source_refs_item_is_refused(strict):
    _refuses(strict, _record(source_refs=[3]))


def test_a_non_string_promoted_from_is_refused(strict):
    _refuses(strict, _record(promoted_from=["doc/observations/observations.yaml"]))


# --- production surfaces ----------------------------------------------------------


def test_the_packaged_template_prescribes_exactly_the_admitted_field_set():
    """Step 3's alignment, as an assertion over the template the toolkit actually renders.

    `templates/observation.md` at the repo root is byte-identical to this packaged copy,
    but the packaged one is what renders -- the pre-registration precedent is that a
    repo-root template can be a stale shadow.

    The template prescribes no `promoted_from`, which is consistent rather than a gap:
    the field is written by promotion, not by scaffolding, and the command that wrote it
    (`science entities triage-aggregate --promote-coined`) no longer exists.
    """
    template = (TEMPLATES / "observation.md").read_text()
    declared = json.loads(json.dumps(_mixin()["properties"]))
    prescribed = {
        line.split(":", 1)[0].strip()
        for line in template.split("---")[1].splitlines()
        if line.strip() and not line.startswith((" ", "\t", "#")) and ":" in line
    }
    prescribed.discard("_template")
    assert prescribed == {
        "id",
        "kind",
        "title",
        "status",
        "related",
        "source_refs",
        "created",
        "updated",
    }
    # Everything the template prescribes is either declared here or admitted by base 2.0.
    base_admitted = {"title", "created", "updated"}
    assert prescribed <= set(declared) | base_admitted


def test_the_template_declares_no_omitted_fields():
    """The `method` slice's zero-occurrence lesson, checked rather than assumed.

    `method`'s template prescribes `stochasticity`/`seed_params` under `{ omit: true }` --
    authored by no record, declared by the model, read by six modules. Omitting them
    would have passed every corpus check while making a shipped programme unauthorable.
    `observation`'s template has no such entry; five sibling templates do, so the pattern
    is live and this kind's absence of it is a fact about this kind.
    """
    assert "omit: true" not in (TEMPLATES / "observation.md").read_text()
    assert "omit: true" in (TEMPLATES / "method.md").read_text(), (
        "control: the pattern exists and this test would notice it"
    )


# --- the mixin's own declaration -------------------------------------------------


def test_mixin_pins_its_own_kind():
    """Gate 2's requirement, asserted here too so the file is self-certifying."""
    assert _mixin()["properties"]["kind"] == {"const": "observation"}


def test_status_declares_no_enum():
    status = _mixin()["properties"]["status"]
    assert status["type"] == "string"
    assert "enum" not in status
    # The key set too, so a `const` or `pattern` smuggling the vocabulary back in is
    # caught by the same test that catches `enum`.
    assert set(status) == {"type", "$comment"}


def test_promoted_from_matches_the_frozen_literal_oracle():
    """Compared against the LITERAL, not against a sibling mixin.

    Pairwise equality between mixins is insufficient: all of them could drift to the same
    wrong value, which repeats the tautology defect one level down. The oracle is
    ~/d/protein-landscape/schemas/extension-protein-landscape-promotion-1.0.json.
    """
    assert _mixin()["properties"]["promoted_from"] == {
        "type": "string",
        "minLength": 1,
        "description": (
            "Path of the source file this entity was promoted from, "
            "e.g. knowledge/sources/local/entities.yaml"
        ),
    }


def test_mixin_declares_exactly_the_frozen_field_set():
    """The step-1 inventory, as an assertion.

    A field added to the mixin without going through the inventory fails here -- which is
    the point. `schema_profile` is present as `false`, the reserved narrowing. `profile`,
    `consolidated_into` and `superseded_by` are ABSENT, and each absence is a ruling with
    its own mutation probe above.
    """
    assert set(_mixin()["properties"]) == {
        "id",
        "kind",
        "status",
        "promoted_from",
        "related",
        "source_refs",
        "schema_profile",
    }
