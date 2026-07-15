"""Project extensions — the ownership contract that lets strictness arrive at all.

`unevaluatedProperties: false` (Task 6) closes the hypothesis schema. Two projects author fields
that are theirs alone: mm30's three assessment labels, and evolution's two provenance keys. Without
an owner for those fields, the only way to keep those repos validating would be to promote a
one-project field into the core mixin for all 22 projects — design §6's ownership contract,
violated. **Strictness and project-local fields must arrive together, or strictness cannot arrive.**

An extension is ADDITIVE ONLY. Composition is a pure `allOf`, so an extension that redefined a core
field would not override it — it would INTERSECT with it, silently yielding a schema nothing can
satisfy. That is rejected at resolve time, by name.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from science_model.entity_schema import (
    EntityValidationError,
    EntityValidator,
    ExtensionContractError,
    ExtensionRedefinesCoreField,
    SchemaLoader,
    default_profile_for_kind,
    resolve_profile,
)


def _h(**over: Any) -> dict[str, Any]:
    base = {
        "id": "hypothesis:0001-x",
        "kind": "hypothesis",
        "title": "T",
        "created": "2026-07-12",
        "updated": "2026-07-12",
        "status": "active",
    }
    base.update(over)
    return base


@pytest.fixture
def tmp_schema_dir(tmp_path: Path) -> Path:
    d = tmp_path / "schemas"
    d.mkdir()
    return d


def _write_extension(schema_dir: Path, filename: str, body: dict[str, Any]) -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://schemas.science/{filename}",
        "type": "object",
        **body,
    }
    (schema_dir / filename).write_text(json.dumps(schema), encoding="utf-8")


def test_an_extension_ADDS_a_field_without_touching_the_core_mixin(tmp_schema_dir: Path) -> None:
    _write_extension(
        tmp_schema_dir,
        "extension-mm30-assessment-1.0.json",
        {"properties": {"confidence_mechanistic_label": {"type": "string"}}},
    )
    loader = SchemaLoader(project_dir=tmp_schema_dir)
    profile = resolve_profile("hypothesis", extensions=["mm30.assessment/1.0"], loader=loader)
    EntityValidator(loader).validate_as(_h(confidence_mechanistic_label="high"), profile)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("confidence_label", "moderate"),  # mm30
        ("confidence_mechanistic_label", "high"),  # mm30
        ("identification", "observational"),  # mm30
        ("external_hypothesis_id", "EH-042"),  # evolution
        ("source_stated_evidence", "barcoded mouse expt"),  # evolution -- the RENAME TARGET
    ],
)
def test_the_SAME_field_is_rejected_WITHOUT_the_extension(field: str, value: str) -> None:
    # This is the whole point: each field is legal for exactly ONE project and illegal everywhere
    # else. If any of these passes without its extension, the mixin swallowed a project field --
    # the defect Task 2 removed nine keys to prevent.
    #
    # `source_stated_evidence` is here because it is the ONLY field in the corpus that Task 9
    # CREATES. Every other key is either already authored or already forbidden; this one is written
    # by the migration itself, so if core silently admitted it, the migration would appear to
    # succeed everywhere and the extension would be dead code that nobody noticed was dead.
    with pytest.raises(EntityValidationError):
        EntityValidator().validate_as(_h(**{field: value}), default_profile_for_kind("hypothesis"))


def test_an_extension_may_NOT_redefine_a_core_field(tmp_schema_dir: Path) -> None:
    # Additive ONLY (design §6). An allOf can only narrow, so a redefinition would silently
    # INTERSECT with the core enum rather than replace it -- producing an unsatisfiable schema
    # rather than an error. Catch it at resolve time, loudly, by name.
    _write_extension(
        tmp_schema_dir,
        "extension-bad-x-1.0.json",
        {"properties": {"status": {"enum": ["whatever"]}}},
    )
    with pytest.raises(ExtensionRedefinesCoreField, match="status"):
        resolve_profile(
            "hypothesis",
            extensions=["bad.x/1.0"],
            loader=SchemaLoader(project_dir=tmp_schema_dir),
        )


def test_an_extension_may_not_redefine_a_BASE_field_either(tmp_schema_dir: Path) -> None:
    # The base owns `id`/`kind`/`title`/`created`/`updated`. A redefinition there intersects just as
    # unsatisfiably as one on a mixin field, so the check must span BOTH allOf branches, not only
    # the mixin.
    _write_extension(
        tmp_schema_dir,
        "extension-bad-base-1.0.json",
        {"properties": {"title": {"type": "integer"}}},
    )
    with pytest.raises(ExtensionRedefinesCoreField, match="title"):
        resolve_profile(
            "hypothesis",
            extensions=["bad.base/1.0"],
            loader=SchemaLoader(project_dir=tmp_schema_dir),
        )


def test_the_evolution_extension_declares_BOTH_of_its_fields(tmp_schema_dir: Path) -> None:
    # `external_hypothesis_id` (evicted from core) and `source_stated_evidence` (the rename target of
    # `author_stated_evidence`). Two projects, two extensions -- and 13 + 13 authored values that
    # vanish the moment the schema closes if either is missing.
    _write_extension(
        tmp_schema_dir,
        "extension-evolution-provenance-1.0.json",
        {
            "properties": {
                "external_hypothesis_id": {"type": "string", "pattern": "^EH-[0-9]+$"},
                "source_stated_evidence": {"type": "string", "pattern": "\\S"},
            }
        },
    )
    loader = SchemaLoader(project_dir=tmp_schema_dir)
    profile = resolve_profile(
        "hypothesis", extensions=["evolution.provenance/1.0"], loader=loader
    )
    EntityValidator(loader).validate_as(
        _h(
            external_hypothesis_id="EH-042",
            source_stated_evidence="established in barcoded mouse experiments",
        ),
        profile,
    )


def test_the_OLD_key_is_dead_even_WITH_the_extension(tmp_schema_dir: Path) -> None:
    # THE test that makes the rename a rename. `author_stated_evidence` is `false` in the core mixin,
    # and `false` inside an allOf is absolute -- no extension can re-admit it. If this ever passes,
    # the corpus has two spellings of one field and the migration silently became optional.
    _write_extension(
        tmp_schema_dir,
        "extension-evolution-provenance-1.0.json",
        {"properties": {"source_stated_evidence": {"type": "string"}}},
    )
    loader = SchemaLoader(project_dir=tmp_schema_dir)
    profile = resolve_profile(
        "hypothesis", extensions=["evolution.provenance/1.0"], loader=loader
    )
    with pytest.raises(EntityValidationError):
        EntityValidator(loader).validate_as(
            _h(author_stated_evidence="established (barcoded mouse experiment)"), profile
        )


def test_zero_extensions_is_exactly_the_default_profile() -> None:
    # `resolve_profile` must not become a second, subtly-different spelling of the default. Task 7,
    # 9 and 10 call it for EVERY project, and 20 of the 22 declare no extensions at all.
    assert resolve_profile("hypothesis", extensions=[]).render() == (
        default_profile_for_kind("hypothesis").render()
    )


@pytest.mark.parametrize(
    ("keyword", "body"),
    [
        # Each of these NARROWS the composed record from inside its own allOf branch, WITHOUT ever
        # naming a core property -- so a `properties`-only check waves every one of them through.
        ("required", {"properties": {"x": {"type": "string"}}, "required": ["verdict"]}),
        ("not", {"properties": {"x": {"type": "string"}}, "not": {"required": ["status"]}}),
        (
            "if",
            {
                "properties": {"x": {"type": "string"}},
                "if": {"properties": {"status": {"const": "active"}}},
                "then": {"required": ["x"]},
            },
        ),
        # `additionalProperties` inside an allOf branch cannot see its SIBLING branches, so it
        # rejects every field the base and the mixin declare -- the whole reason the validator
        # composes with `unevaluatedProperties` instead.
        (
            "additionalProperties",
            {"properties": {"x": {"type": "string"}}, "additionalProperties": False},
        ),
        ("$ref", {"properties": {"x": {"type": "string"}}, "$ref": "#/$defs/anything"}),
        (
            "allOf",
            {"properties": {"x": {"type": "string"}}, "allOf": [{"required": ["verdict"]}]},
        ),
        (
            "dependentRequired",
            {"properties": {"x": {"type": "string"}}, "dependentRequired": {"x": ["verdict"]}},
        ),
    ],
)
def test_a_root_applicator_cannot_narrow_the_composed_record(
    tmp_schema_dir: Path, keyword: str, body: dict[str, Any]
) -> None:
    # "Additive only" is NOT enforced by checking `properties` against core. Every payload here
    # leaves `properties` perfectly clean and still constrains the composed record -- `required:
    # ["verdict"]` makes a core field mandatory for one project; `not`/`if` forbid records the core
    # admits. The contract is an ALLOW-list precisely so a keyword nobody thought of cannot slip
    # through the gap a deny-list would leave.
    _write_extension(tmp_schema_dir, "extension-bad-root-1.0.json", body)
    with pytest.raises(ExtensionContractError, match=re.escape(keyword)):
        resolve_profile(
            "hypothesis",
            extensions=["bad.root/1.0"],
            loader=SchemaLoader(project_dir=tmp_schema_dir),
        )


def test_two_extensions_may_not_both_own_one_field(tmp_schema_dir: Path) -> None:
    # The core-collision defect one level out: two extensions declaring `shared` INTERSECT their
    # constraints, and neither owner can see the other's. There is no rule for merging two owners,
    # so the second claimant is an error.
    _write_extension(
        tmp_schema_dir, "extension-a-one-1.0.json", {"properties": {"shared": {"type": "string"}}}
    )
    _write_extension(
        tmp_schema_dir, "extension-b-two-1.0.json", {"properties": {"shared": {"type": "integer"}}}
    )
    with pytest.raises(ExtensionContractError, match="shared"):
        resolve_profile(
            "hypothesis",
            extensions=["a.one/1.0", "b.two/1.0"],
            loader=SchemaLoader(project_dir=tmp_schema_dir),
        )


def test_an_extension_MAY_require_a_field_it_owns(tmp_schema_dir: Path) -> None:
    # The control. The contract forbids requiring a CORE field, not requiring your own -- a project
    # is entitled to say "if you use my extension, this field of mine is mandatory."
    _write_extension(
        tmp_schema_dir,
        "extension-ok-own-1.0.json",
        {"properties": {"mine": {"type": "string"}}, "required": ["mine"]},
    )
    loader = SchemaLoader(project_dir=tmp_schema_dir)
    profile = resolve_profile("hypothesis", extensions=["ok.own/1.0"], loader=loader)
    EntityValidator(loader).validate_as(_h(mine="present"), profile)
    with pytest.raises(EntityValidationError):
        EntityValidator(loader).validate_as(_h(), profile)


def test_a_project_schema_dir_does_not_shadow_a_PACKAGE_schema(tmp_schema_dir: Path) -> None:
    # The project dir is searched FIRST, so a project could otherwise drop in its own
    # `mixin-hypothesis-1.0.json` and silently redefine the core kind for itself -- re-opening the
    # per-project divergence this whole arc exists to close. Only extensions may come from a project.
    (tmp_schema_dir / "mixin-hypothesis-1.0.json").write_text(
        json.dumps({"type": "object", "properties": {"status": {"enum": ["anything"]}}}),
        encoding="utf-8",
    )
    loader = SchemaLoader(project_dir=tmp_schema_dir)
    EntityValidator(loader).validate_as(_h(status="active"), default_profile_for_kind("hypothesis"))
    with pytest.raises(EntityValidationError):
        EntityValidator(loader).validate_as(
            _h(status="anything"), default_profile_for_kind("hypothesis")
        )
