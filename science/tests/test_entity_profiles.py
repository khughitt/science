"""`entity_extensions:` in science.yaml — the project side of the ownership contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from science_model.entity_schema import EntityValidationError, ExtensionContractError

from science_tool.entity_profiles import EntityExtensionsError, load_project_schema
from science_tool.project_config import load_project_config

EXTENSION = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://schemas.science/extension-mm30-assessment-1.0.json",
    "type": "object",
    "properties": {"confidence_mechanistic_label": {"type": "string", "pattern": "\\S"}},
}


def _project(root: Path, *, extensions: dict[str, list[str]] | None = None) -> Path:
    config: dict[str, object] = {"name": "p", "id": "p"}
    if extensions is not None:
        config["entity_extensions"] = extensions
    (root / "science.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    return root


def _hypothesis(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "hypothesis:0001-x",
        "kind": "hypothesis",
        "title": "T",
        "created": "2026-07-12",
        "updated": "2026-07-12",
        "status": "active",
    }
    base.update(over)
    return base


def test_entity_extensions_is_a_DECLARED_field_not_an_extra(tmp_path: Path) -> None:
    # ProjectConfig is `extra="allow"`, so an UNDECLARED `entity_extensions` would be accepted,
    # ignored, and silently do nothing -- the exact failure mode (a key that validates and is then
    # dropped) that this whole schema convergence exists to close. Declaring it is the fix.
    _project(tmp_path, extensions={"hypothesis": ["mm30.assessment/1.0"]})
    config = load_project_config(tmp_path)
    assert config.entity_extensions == {"hypothesis": ["mm30.assessment/1.0"]}


def test_a_project_with_no_stanza_gets_the_plain_core_profile(tmp_path: Path) -> None:
    # 20 of the 22 projects declare nothing. They must not pay for this feature.
    _project(tmp_path)
    schema = load_project_schema(tmp_path)
    assert schema.profile_for("hypothesis").render() == "science-entity-base/2.0+hypothesis/1.0"


def test_a_declared_extension_is_resolved_from_the_project_schemas_dir(tmp_path: Path) -> None:
    _project(tmp_path, extensions={"hypothesis": ["mm30.assessment/1.0"]})
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "extension-mm30-assessment-1.0.json").write_text(
        json.dumps(EXTENSION), encoding="utf-8"
    )

    schema = load_project_schema(tmp_path)
    profile = schema.profile_for("hypothesis")
    assert profile.render() == (
        "science-entity-base/2.0+hypothesis/1.0+mm30.assessment/1.0"
    )
    schema.validator.validate_as(_hypothesis(confidence_mechanistic_label="high"), profile)


def test_the_field_is_STILL_rejected_in_a_project_that_did_not_declare_it(tmp_path: Path) -> None:
    # The field is mm30's. A neighbouring project that authors it gets an error, not a free pass.
    _project(tmp_path)
    schema = load_project_schema(tmp_path)
    with pytest.raises(EntityValidationError):
        schema.validator.validate_as(
            _hypothesis(confidence_mechanistic_label="high"), schema.profile_for("hypothesis")
        )


def test_a_MISSPELLED_kind_is_an_error_not_a_silent_no_op(tmp_path: Path) -> None:
    # `hypothsis` -- one letter out. Nothing ever reads that key, so without eager certification the
    # stanza sits in science.yaml forever, matching no kind, protecting nothing, and looking exactly
    # like a project whose fields ARE protected. The declaration is a claim; an unread claim is not
    # a claim.
    _project(tmp_path, extensions={"hypothsis": ["mm30.assessment/1.0"]})
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "extension-mm30-assessment-1.0.json").write_text(
        json.dumps(EXTENSION), encoding="utf-8"
    )
    with pytest.raises(EntityExtensionsError, match="hypothsis"):
        load_project_schema(tmp_path)


def test_a_declared_extension_with_NO_schema_file_is_an_error(tmp_path: Path) -> None:
    # Declared, never written. Without eager resolution this surfaces only at the first validation
    # of a hypothesis that happens to author one of the fields -- i.e. possibly never.
    _project(tmp_path, extensions={"hypothesis": ["mm30.assessment/1.0"]})
    with pytest.raises(EntityExtensionsError, match="does not exist"):
        load_project_schema(tmp_path)


def test_a_project_extension_does_NOT_fall_back_to_a_PACKAGED_schema(tmp_path: Path) -> None:
    # The explicit ruling. `bio.rnaseq` IS a packaged extension, and the loader searches the project
    # dir first and then the package -- so a silent fallback would let a project whose own schema
    # file is missing or misnamed quietly validate against a TOOLKIT schema of the same name: a
    # field it does not own, under a contract it cannot see. A project extension must be a schema
    # the project OWNS.
    _project(tmp_path, extensions={"hypothesis": ["bio.rnaseq/1.0"]})
    (tmp_path / "schemas").mkdir()
    with pytest.raises(EntityExtensionsError, match="does not exist"):
        load_project_schema(tmp_path)


def test_a_malformed_component_is_an_error(tmp_path: Path) -> None:
    # No version. `mm30.assessment` alone names no versioned schema.
    _project(tmp_path, extensions={"hypothesis": ["mm30.assessment"]})
    with pytest.raises(EntityExtensionsError, match="malformed"):
        load_project_schema(tmp_path)


def test_the_root_contract_is_enforced_at_PROJECT_LOAD(tmp_path: Path) -> None:
    # The contract lives in the model layer, but it has to FIRE here -- at the boundary where a
    # project's own file is read. An extension requiring a core field would otherwise be discovered
    # only when some entity happened to be validated.
    _project(tmp_path, extensions={"hypothesis": ["mm30.assessment/1.0"]})
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "extension-mm30-assessment-1.0.json").write_text(
        json.dumps({**EXTENSION, "required": ["verdict"]}), encoding="utf-8"
    )
    with pytest.raises(ExtensionContractError, match="verdict"):
        load_project_schema(tmp_path)
