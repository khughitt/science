"""Probes for the DORMANT `mixin-method-1.0` schema.

Step 2 of the method slice. The mixin exists on disk but no generation row selects
it and `schema_closed` is still False, so nothing here changes what the toolkit
loads today. These probes fix the candidate contract before the production surfaces
are aligned to it.

Every strict probe composes the candidate profile through the REAL
`EntityValidator._compose` (via `validate_as`). Hand-rolling
`{"allOf": [...], "unevaluatedProperties": False}` here instead would certify this
test file's idea of composition rather than the toolkit's.

Arming a kind flips TWO independent lookups, and the fixture patches both because
step 7 will satisfy both from one declaration:

- `validator.py:135` gates `unevaluatedProperties: false` on `PROJECT_MIXIN_NAMES`;
- `loader.py:92` gates the `mixin-` filename prefix on `TYPE_MIXIN_NAMES`, so an
  unarmed name resolves to `extension-method-1.0.json` and is not found at all.

Both are patched in the CONSUMING module's namespace, not in `profile`: each does
`from ...profile import <NAME>`, which binds a new name at import time, so rebinding
the source module would not be seen.
"""

import json
from datetime import date
from pathlib import Path

import pytest
import yaml
from science_model.entity_schema import loader as loader_module
from science_model.entity_schema import validator as validator_module
from science_model.entity_schema.loader import SchemaNotFoundError
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
from science_model.templates import Renderer

SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"

CANDIDATE = ProfileString(
    base=ProfileComponent(BASE_NAME, "2.0"),
    mixin=ProfileComponent("method", "1.0"),
    extensions=(),
)

# The frozen literal oracle for `promoted_from`, transcribed from
# ~/d/protein-landscape/schemas/extension-protein-landscape-promotion-1.0.json.
# Hand-authored here on purpose: comparing this mixin against another MIXIN would let
# every admitting mixin drift to the same wrong value together, which is the tautology
# defect one level down.
PROMOTED_FROM_ORACLE = {
    "type": "string",
    "minLength": 1,
    "description": (
        "Path of the source file this entity was promoted from, "
        "e.g. knowledge/sources/local/entities.yaml"
    ),
}


def _mixin() -> dict:
    return json.loads((SCHEMAS / "mixin-method-1.0.json").read_text())


def _record(**overrides) -> dict:
    """A minimal record every one of the 51 authored methods satisfies."""
    record = {
        "id": "method:null-model",
        "kind": "method",
        "title": "Null model",
        "status": "active",
        "created": "2026-06-10",
        "updated": "2026-06-10",
    }
    record.update(overrides)
    return record


@pytest.fixture
def strict(monkeypatch) -> EntityValidator:
    """An EntityValidator that composes `method` STRICTLY, as step 7 eventually will."""
    monkeypatch.setattr(
        validator_module, "PROJECT_MIXIN_NAMES", PROJECT_MIXIN_NAMES | {"method"}
    )
    monkeypatch.setattr(loader_module, "TYPE_MIXIN_NAMES", TYPE_MIXIN_NAMES | {"method"})
    return EntityValidator()


def _refuses(validator: EntityValidator, record: dict) -> str:
    with pytest.raises(EntityValidationError) as caught:
        validator.validate_as(record, CANDIDATE)
    return str(caught.value)


# --- dormant: these four INVERT at step 7 ----------------------------------------
#
# Written in the dormant direction on purpose. Each asserts the mixin is currently
# inert, and each is flipped in the slice's final commit -- so the arming edit cannot
# land silently. Arming touches two independent lookups, the composer's
# `PROJECT_MIXIN_NAMES` and the loader's `TYPE_MIXIN_NAMES`, and both will derive from
# `schema_closed=True` on the descriptor so the pair cannot drift apart.


def test_method_is_not_yet_armed():
    assert "method" not in PROJECT_MIXIN_NAMES
    assert "method" not in TYPE_MIXIN_NAMES


def test_no_generation_row_selects_the_method_mixin():
    """Step 7 adds `method` to BOTH rows, at the same version.

    Neither detail is incidental: all five method-carrying projects pin generation 3,
    but `sources.py:1704` calls `default_profile_for_kind(entity.kind)` with no
    generation argument and therefore always resolves row 2. The two rows agreeing on
    `1.0` is what keeps that call site consistent with the projects it resolves for.
    """
    with pytest.raises(ProfileParseError):
        default_profile_for_kind("method")


def test_the_mixin_is_not_yet_reachable_as_a_mixin():
    """`loader.py:92` derives the filename prefix from `TYPE_MIXIN_NAMES`.

    While dormant this resolves to `extension-method-1.0.json`: the file on disk is not
    lax, it is UNREACHABLE. A slice that mistook this for "already passing" would arm
    nothing and certify everything.
    """
    with pytest.raises(SchemaNotFoundError):
        EntityValidator().validate_as(_record(), CANDIDATE)


def test_composition_does_not_close_yet(strict):
    """The defect this slice closes, asserted against the real composer.

    Unarmed, `_compose` omits `unevaluatedProperties` -- but the mixin is unreachable
    while dormant, so the honest dormant-side assertion is that the STRICT fixture is
    what refuses the shadow key, and the default validator cannot even load the file.
    At step 7 this becomes `EntityValidator()` with no fixture.
    """
    assert "shadow_key" in _refuses(strict, _record(shadow_key="unvouched"))


# --- value probes: the measured corpus validates ---------------------------------


def test_minimal_authored_record_validates(strict):
    strict.validate_as(_record(), CANDIDATE)


def test_record_with_every_observed_non_base_field_validates(strict):
    strict.validate_as(
        _record(
            profile="local",
            promoted_from="knowledge/sources/local/terms.yaml",
            related=["task:t662"],
            source_refs=["cite:Wu2017MM3D"],
            datasets=["MMRF CoMMpass IA18/IA22"],
            aliases=["tool:metapredict"],
        ),
        CANDIDATE,
    )


def test_base_admitted_fields_still_validate(strict):
    """`description` (4 records) and `ontology_terms` (12) come from base 2.0.

    The mixin declares neither. If a future edit narrowed a base field away for this
    kind, this is what would catch it.
    """
    strict.validate_as(
        _record(description="Fast disorder predictor.", ontology_terms=["MYC gene"]),
        CANDIDATE,
    )


@pytest.mark.parametrize(
    "value",
    [
        "knowledge/sources/local/terms.yaml",
        "knowledge/sources/local/entities.yaml",
    ],
)
def test_every_promoted_from_value_in_the_corpus_validates(strict, value):
    """The two distinct values across the 20 methods that carry the field."""
    strict.validate_as(_record(promoted_from=value), CANDIDATE)


def test_the_only_authored_profile_value_validates(strict):
    """All 4 are `local`. `core` -- ProjectEntity's default -- is deliberately not
    probed: no method record carries it, so a probe on it would pass on the model
    default rather than on authored data."""
    strict.validate_as(_record(profile="local"), CANDIDATE)


# --- the status ruling, in executable form ---------------------------------------


def test_a_status_outside_the_descriptor_vocabulary_still_validates(strict):
    """THE ruling of this slice, and the one place it departs from `concept`.

    cbioportal's `method:length-aware-geneset-enrichment` carries `status: proposed`,
    which is not in the descriptor's vocabulary (profiles/core.py:504). `method` is not
    in `_CERTIFIED_KINDS` (validate/kind_severity.py:24), and `status_vocabulary.py`
    rules that an uncertified instrument may not fail anyone's build -- so closure must
    not refuse this record at load. The finding stays where it belongs: a
    `method.status-vocabulary` WARN.

    Flip this to a refusal only when `method` joins `_CERTIFIED_KINDS`.
    """
    strict.validate_as(_record(status="proposed"), CANDIDATE)


@pytest.mark.parametrize("value", ["active", "superseded", "retired", "archived"])
def test_every_descriptor_status_validates(strict, value):
    strict.validate_as(_record(status=value), CANDIDATE)


def test_non_string_status_is_refused(strict):
    """No enum does not mean no type. The shape is still closed."""
    _refuses(strict, _record(status=3))


# --- the zero-occurrence fields ---------------------------------------------------


@pytest.mark.parametrize(
    "value", ["deterministic", "seedable", "nondeterministic"]
)
def test_every_stochasticity_value_validates(strict, value):
    """ZERO records author this field. It is admitted because the TEMPLATE prescribes
    it (`{ omit: true }`), `MethodEntity` declares it, and six production readers
    consume it -- the procedure's zero-occurrence case."""
    strict.validate_as(_record(stochasticity=value), CANDIDATE)


def test_the_stochasticity_enum_matches_the_model():
    """A value added to `Stochasticity` in Python without regenerating this enum fails
    here rather than at some project's load."""
    from science_model.entities import Stochasticity

    assert set(_mixin()["properties"]["stochasticity"]["enum"]) == {
        s.value for s in Stochasticity
    }


def test_foreign_stochasticity_is_refused(strict):
    _refuses(strict, _record(stochasticity="mostly-deterministic"))


def test_explicit_null_stochasticity_is_refused(strict):
    """ABSENCE already means unclassified (MethodEntity's docstring). Admitting an
    explicit null would be a second spelling of absence -- the defect
    `mixin-hypothesis-2.0` refuses by name when it excludes `proposed` from `verdict`.
    """
    _refuses(strict, _record(stochasticity=None))


def test_seedable_with_empty_seed_params_validates(strict):
    """The state every seedable method in the live corpus is in.
    `validate/checks/methods.py` reports it as a WARN; the schema must not promote that
    warning to a hard failure, which is why `seed_params` carries no `minItems`."""
    strict.validate_as(_record(stochasticity="seedable", seed_params=[]), CANDIDATE)


def test_seed_params_accepts_named_parameters(strict):
    strict.validate_as(_record(seed_params=["random_state", "seed"]), CANDIDATE)


def test_non_string_seed_param_is_refused(strict):
    _refuses(strict, _record(seed_params=[3]))


# --- mutation probes: what the closed schema must refuse -------------------------


def test_undeclared_key_is_refused(strict):
    assert "shadow_key" in _refuses(strict, _record(shadow_key="unvouched"))


def test_foreign_kind_is_refused(strict):
    _refuses(strict, _record(kind="hypothesis"))


def test_foreign_id_prefix_is_refused(strict):
    """`kind` alone would pass; the id would name a different entity."""
    _refuses(strict, _record(id="dataset:null-model"))


def test_missing_status_is_refused(strict):
    record = _record()
    del record["status"]
    _refuses(strict, record)


def test_authored_schema_profile_is_refused(strict):
    """The narrowing: `profile` is the authored field, `schema_profile` its derived one."""
    _refuses(strict, _record(schema_profile=f"{BASE_NAME}/2.0+method/1.0"))


def test_empty_promoted_from_is_refused(strict):
    """`minLength: 1` -- a promotion from nowhere is not a promotion."""
    _refuses(strict, _record(promoted_from=""))


def test_non_string_promoted_from_is_refused(strict):
    _refuses(strict, _record(promoted_from=3))


def test_scalar_related_is_refused(strict):
    _refuses(strict, _record(related="task:t662"))


def test_non_string_related_item_is_refused(strict):
    _refuses(strict, _record(related=[3]))


def test_scalar_aliases_is_refused(strict):
    _refuses(strict, _record(aliases="tool:metapredict"))


def test_scalar_datasets_is_refused(strict):
    _refuses(strict, _record(datasets="MMRF CoMMpass"))


# --- production surfaces: the template is the only one that emits method keys -----


def _rendered_frontmatter() -> dict:
    """Render `method` through the PACKAGED template, which is what production uses.

    `entities.py:796` imports `Renderer` from `science_model.templates`, so the
    repo-root `templates/method.md` is a second copy that renders nothing. It is kept
    honest by `test_templates.py::test_root_and_packaged_migrated_templates_match`,
    which byte-compares the two for every `template_ready` kind -- so asserting on the
    packaged one here covers both, and asserting on the root copy would cover neither.
    """
    text = Renderer(today=date(2026, 5, 3)).render(
        "method",
        fields={
            "entity_id": "method:null-model",
            "kind": "method",
            "title": "Null model",
            "status": "active",
            "related": [],
            "source_refs": [],
            "slug": "null-model",
            "local_part": "null-model",
            "created": "2026-05-03",
            "updated": "2026-05-03",
        },
    )
    return yaml.safe_load(text.split("---")[1])


def test_the_rendered_template_validates_under_the_candidate(strict):
    """The scaffold a new method starts from must satisfy the schema that will judge it.

    This is the failure the slice procedure names: templates emitting a field set
    nothing enforces. Asserted in the direction that catches it -- add a key to
    `templates/method.md` that the mixin does not admit and this goes red.
    """
    strict.validate_as(_rendered_frontmatter(), CANDIDATE)


def test_the_template_emits_no_field_outside_the_frozen_set():
    """Narrower and louder than the validation above: names the drift rather than
    reporting `unevaluatedProperties`."""
    assert set(_rendered_frontmatter()) == {
        "id",
        "kind",
        "title",
        "status",
        "ontology_terms",
        "datasets",
        "source_refs",
        "related",
        "created",
        "updated",
    }


def test_the_templates_omitted_fields_are_admitted_by_the_mixin():
    """`stochasticity` and `seed_params` are declared by the template under
    `{ omit: true }` -- part of the kind's frontmatter contract, never rendered
    (templates.py:243). A closure that inventoried only RENDERED keys would drop both
    and make the shipped method-stochasticity program unauthorable."""
    template = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "science_model"
        / "templates"
        / "method.md"
    ).read_text()
    declared = yaml.safe_load(template.split("---")[1])["_template"]["frontmatter"]
    omitted = {name for name, policy in declared.items() if policy.get("omit")}
    assert omitted == {"stochasticity", "seed_params"}
    assert omitted <= set(_mixin()["properties"])


# --- the mixin's own declaration -------------------------------------------------


def test_promoted_from_matches_the_frozen_oracle():
    assert _mixin()["properties"]["promoted_from"] == PROMOTED_FROM_ORACLE


def test_mixin_pins_its_own_kind():
    """Gate 2's requirement, asserted here too so the file is self-certifying."""
    assert _mixin()["properties"]["kind"] == {"const": "method"}


def test_status_is_not_enum_locked():
    """The ruling, asserted against the declaration itself rather than its behaviour.

    A future edit that adds an enum here -- before `method` joins `_CERTIFIED_KINDS` --
    fails on this line with the reason attached, not on some project's load.
    """
    assert "enum" not in _mixin()["properties"]["status"]


def test_mixin_declares_exactly_the_frozen_field_set():
    """The step-1 inventory, as an assertion.

    A field added to the mixin without going through the inventory fails here -- which
    is the point. `schema_profile` is present as `false`, the reserved narrowing.
    """
    assert set(_mixin()["properties"]) == {
        "id",
        "kind",
        "status",
        "profile",
        "promoted_from",
        "stochasticity",
        "seed_params",
        "related",
        "source_refs",
        "datasets",
        "aliases",
        "schema_profile",
    }
