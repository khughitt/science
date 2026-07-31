"""Probes for the DORMANT `mixin-finding-1.0` schema.

Authored dormant in step 2; step 7 arms it and flips the four `dormant` tests below.
While dormant no generation row selects this mixin and `schema_closed=False` on the
descriptor, so nothing here changes what the toolkit loads.

Every strict probe composes the candidate profile through the REAL
`EntityValidator._compose` (via `validate_as`). Hand-rolling
`{"allOf": [...], "unevaluatedProperties": False}` here instead would certify this
test file's idea of composition rather than the toolkit's.

Arming a kind flips TWO independent lookups, and the `strict` fixture patches both
because step 7 will satisfy both from ONE declaration (`schema_closed=True`):

- `validator.py:135` gates `unevaluatedProperties: false` on `PROJECT_MIXIN_NAMES`;
- `loader.py:92` gates the `mixin-` filename prefix on `TYPE_MIXIN_NAMES`, so an
  unarmed name resolves to `extension-finding-1.0.json` and is not found at all.
  An unarmed mixin is UNREACHABLE, not lax -- the distinction the slice procedure
  insists on, and the reason the patch-based simulation here is never a substitute
  for step 7.

Both are patched in the CONSUMING module's namespace, not in `profile`: each does
`from ...profile import <NAME>`, which binds a new name at import time, so rebinding
the source module would not be seen.

`finding` is the first kind whose records reach the schema by two structurally
different paths, so the value probes come in two families -- `_record()` for the 52
markdown records and `_source_record()` for the 149 structured rows. A probe family
that covered only one of them would certify half the corpus.
"""

import json
from pathlib import Path

import pytest
from science_model.entity_schema import loader as loader_module
from science_model.entity_schema.loader import SchemaNotFoundError
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

CANDIDATE = ProfileString(
    base=ProfileComponent(BASE_NAME, "2.0"),
    mixin=ProfileComponent("finding", "1.0"),
    extensions=(),
)


def _mixin() -> dict:
    return json.loads((SCHEMAS / "mixin-finding-1.0.json").read_text())


def _record(**overrides) -> dict:
    """A minimal record every one of the 52 authored MARKDOWN findings satisfies."""
    record = {
        "id": "finding:0005-equiv-calibration-full",
        "kind": "finding",
        "title": "Full equivalence calibration calibrates 71/74 strata",
        "status": "active",
        "created": "2026-06-21",
        "updated": "2026-06-21",
    }
    record.update(overrides)
    return record


def _source_record(**overrides) -> dict:
    """A structured row as it reaches the schema, POST-migration.

    `status` and `updated` are present because the step-3 migration puts them there;
    before it, all 149 rows lack both. `file_path` is here because the row authors
    `source_path` and normalization renames it -- so it faces the schema as authored,
    unlike on the markdown path where it is declared injected.
    """
    record = {
        "id": "finding:t291-path2-audit-asep__burgers-equation__heat-equation",
        "kind": "finding",
        "title": "Path-2 audit: asep -> burgers-equation -> heat-equation = invalid",
        "status": "active",
        "created": "2026-04-30",
        "updated": "2026-04-30",
        "profile": "project_specific",
        "file_path": "knowledge/sources/project_specific/finding.yaml",
        "description": "At least one step is not a strict parameter_limit edge.",
        "evidence_refs": ["limit-relation:asep__burgers-equation__a"],
        "related": [],
        "source_refs": [],
        "aliases": [],
        "ontology_terms": [],
    }
    record.update(overrides)
    return record


@pytest.fixture
def strict(monkeypatch) -> EntityValidator:
    """An EntityValidator that composes `finding` STRICTLY, as production will."""
    monkeypatch.setattr(
        validator_module, "PROJECT_MIXIN_NAMES", PROJECT_MIXIN_NAMES | {"finding"}
    )
    monkeypatch.setattr(loader_module, "TYPE_MIXIN_NAMES", TYPE_MIXIN_NAMES | {"finding"})
    return EntityValidator()


def _refuses(validator: EntityValidator, record: dict) -> str:
    with pytest.raises(EntityValidationError) as caught:
        validator.validate_as(record, CANDIDATE)
    return str(caught.value)


# --- dormant: written INVERTED, flipped by the step-7 arming commit ----------------


def test_finding_is_NOT_yet_armed():
    """Flipped at step 7. Until then neither lookup knows the kind."""
    assert "finding" not in PROJECT_MIXIN_NAMES
    assert "finding" not in TYPE_MIXIN_NAMES


@pytest.mark.parametrize("generation", [2, 3])
def test_no_generation_row_selects_the_finding_mixin_yet(generation):
    """Flipped at step 7, when BOTH rows gain `finding: 1.0` in one edit.

    Both rows, and not one: `sources.py` calls `default_profile_for_kind(entity.kind)`
    with no generation argument and always resolves row 2, so a row-3-only arming would
    leave that call site resolving a profile the descriptor claims is closed. That risk
    is live rather than theoretical for THIS kind -- ~/d/natural-systems is pinned to
    generation 2 and holds 172 of the 201 records, while the other two roots are gen 3.
    """
    with pytest.raises(ProfileParseError):
        default_profile_for_kind("finding", generation=generation)


def test_the_mixin_is_not_yet_reachable_as_a_mixin():
    """`loader.py:92` derives the filename prefix from `TYPE_MIXIN_NAMES`.

    While dormant this resolves `extension-finding-1.0.json`, which does not exist: the
    file on disk is not lax, it is UNREACHABLE. Flipped at step 7 to assert the record
    validates.

    The exception type is named rather than caught as `Exception`: a bare `Exception`
    here would also pass if the record were merely INVALID, which is the opposite of
    what this test claims.
    """
    with pytest.raises(SchemaNotFoundError, match="extension-finding-1.0.json"):
        EntityValidator().validate_as(_record(), CANDIDATE)


def test_composition_does_not_yet_close(monkeypatch):
    """The defect this slice closes, demonstrated against the real composer.

    Only the LOADER is patched here, isolating the second lookup: the mixin is found,
    but `unevaluatedProperties: false` is not applied because `finding` is absent from
    `PROJECT_MIXIN_NAMES`. An undeclared key sails through -- which is what "preserved
    unvouched" means for this kind. Flipped at step 7 to assert refusal.
    """
    monkeypatch.setattr(loader_module, "TYPE_MIXIN_NAMES", TYPE_MIXIN_NAMES | {"finding"})
    EntityValidator().validate_as(_record(shadow_key="unvouched"), CANDIDATE)


# --- the frozen field set -------------------------------------------------------


def test_mixin_declares_exactly_the_frozen_field_set():
    assert set(_mixin()["properties"]) == {
        "id",
        "kind",
        "status",
        "profile",
        "file_path",
        "related",
        "source_refs",
        "aliases",
        "evidence_refs",
        "propositions",
        "observations",
        "mode",
        "input",
        "relations",
        "promoted_from",
        "superseded_by",
        "schema_profile",
    }


def test_status_is_required_which_is_this_slices_own_ruling():
    """Not inherited: requiring it is what forces the 149-row source migration."""
    assert _mixin()["required"] == ["id", "kind", "status"]


def test_status_carries_no_enum():
    """`finding` is not in _CERTIFIED_KINDS, so the vocabulary may not be enum-locked."""
    assert "enum" not in _mixin()["properties"]["status"]


def test_mode_carries_no_enum():
    """Same rule, applied to the other free-vocabulary field this kind admits."""
    assert "enum" not in _mixin()["properties"]["mode"]


def test_promoted_from_matches_the_frozen_literal_oracle():
    """Pairwise equality between mixins is insufficient -- all could drift together."""
    assert _mixin()["properties"]["promoted_from"] == {
        "type": "string",
        "minLength": 1,
        "description": (
            "Path of the source file this entity was promoted from, "
            "e.g. knowledge/sources/local/entities.yaml"
        ),
    }


def test_authored_relation_is_copied_verbatim_from_hypothesis_2_0():
    """A finding-local variant is exactly what the `note` ruling refused to write."""
    hypothesis = json.loads((SCHEMAS / "mixin-hypothesis-2.0.json").read_text())
    mine = _mixin()["$defs"]["authored_relation"]
    theirs = hypothesis["$defs"]["authored_relation"]
    assert {k: v for k, v in mine.items() if k != "$comment"} == {
        k: v for k, v in theirs.items() if k != "$comment"
    }


# --- value probes: the measured MARKDOWN corpus validates ------------------------


def test_the_minimal_markdown_record_validates(strict):
    strict.validate_as(_record(), CANDIDATE)


def test_a_fully_populated_markdown_record_validates(strict):
    """Every markdown-path field at once, with the shapes the corpus actually uses."""
    strict.validate_as(
        _record(
            profile="local",
            related=["hypothesis:0007-empirical-fidelity-alignment"],
            source_refs=["dataset:arxiv-formula-equivalence"],
            aliases=["f05"],
            propositions=["proposition:concept-a-affects-concept-b"],
            observations=["observation:x"],
            mode="empirical-measurement",
            input="data/processed/arxiv/catalog/catalog.parquet",
            promoted_from="knowledge/sources/local/entities.yaml",
            description="A finding.",
            relations=[
                {
                    "predicate": "sci:amends",
                    "target": "finding:0016-curated-catalog-vs-a-10-000-paper",
                }
            ],
        ),
        CANDIDATE,
    )


@pytest.mark.parametrize(
    "mode", ["empirical-measurement", "confirmatory", "structural-audit", "literature-synthesis"]
)
def test_every_mode_value_in_the_corpus_validates(strict, mode):
    strict.validate_as(_record(mode=mode), CANDIDATE)


def test_a_relations_entry_may_carry_graph_layer(strict):
    strict.validate_as(
        _record(
            relations=[
                {"predicate": "sci:amends", "target": "finding:0016-x", "graph_layer": "graph/knowledge"}
            ]
        ),
        CANDIDATE,
    )


# --- value probes: the measured STRUCTURED corpus validates ----------------------


def test_the_migrated_structured_row_validates(strict):
    """POST-migration. The pre-migration shape is asserted refused below."""
    strict.validate_as(_source_record(), CANDIDATE)


def test_the_structured_id_shape_validates(strict):
    """`finding:t291-path2-audit-<model>__<model>__<model>` -- why the pattern is prefix-only.

    A numeric-slug pattern derived from the 52 markdown ids would refuse all 149 of these.
    """
    strict.validate_as(
        _source_record(id="finding:t291-path2-audit-bidomain-model__cable-equation__hodgkin-huxley"),
        CANDIDATE,
    )


# --- mutation probes: the omissions and the migration, with teeth ----------------


def test_a_structured_row_without_updated_is_refused(strict):
    """Gate 3, and the reason the migration is not optional.

    All 149 rows are in this state today. base 2.0 requires `updated`, so arming without
    migrating would refuse every one of them.
    """
    row = _source_record()
    del row["updated"]
    assert "updated" in _refuses(strict, row)


def test_a_structured_row_without_status_is_refused(strict):
    """The slice's own ruling, with teeth. All 149 rows are in this state today."""
    row = _source_record()
    del row["status"]
    assert "status" in _refuses(strict, row)


def test_consolidated_into_is_refused(strict):
    """The omission, enforcing the observation slice's writer ruling.

    `finding`'s statuses include `archived`, so consolidate.py stamps this key onto a
    member's frontmatter. The archive INDEX is the only thing that reads it, and
    `unarchive` strips it (archive.py:292) rather than the schema admitting it.
    """
    assert "consolidated_into" in _refuses(
        strict, _record(status="archived", consolidated_into="synthesis:0001-d")
    )


def test_a_relation_note_is_refused(strict):
    """The corpus migration, with teeth.

    3 records author this today and `AuthoredTargetedRelation` silently discards it.
    After the migration the schema refuses it, turning the discard into a load failure.
    """
    assert "note" in _refuses(
        strict,
        _record(
            relations=[
                {"predicate": "sci:amends", "target": "finding:0016-x", "note": "why it amends"}
            ]
        ),
    )


def test_a_relation_without_a_target_is_refused(strict):
    assert "target" in _refuses(
        strict, _record(relations=[{"predicate": "sci:amends"}])
    )


def test_an_id_without_the_finding_prefix_is_refused(strict):
    """Without this the `kind` const passes while the id names a different entity."""
    assert _refuses(strict, _record(id="dataset:arxiv-formula-equivalence"))


def test_superseded_by_must_name_a_finding(strict):
    assert _refuses(strict, _record(superseded_by="hypothesis:0007-x"))


def test_superseded_by_naming_a_finding_validates(strict):
    """The F7 shape, admitted. A supersedable kind whose mixin refused this would be a
    writer that produces records its own schema rejects."""
    strict.validate_as(
        _record(status="superseded", superseded_by="finding:0021-x"), CANDIDATE
    )


def test_an_undeclared_key_is_refused(strict):
    assert "shadow_key" in _refuses(strict, _record(shadow_key="unvouched"))


def test_schema_profile_is_refused(strict):
    assert _refuses(strict, _record(schema_profile="anything"))
