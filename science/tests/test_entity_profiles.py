"""`entity_extensions:` in science.yaml — the project side of the ownership contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from science_model.entity_schema import EntityValidationError

from science_tool.entity_profiles import load_project_schema
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
