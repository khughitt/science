"""The kind vocabulary is derivable, so downstream configs stop transcribing it.

fb-2026-07-26-017: a project's hand-written commitlint `type-enum` listed 24 of
the kinds and went stale, rejecting a legitimate `dataset:` commit.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_model.profiles import CORE_PROFILE
from science_tool.entities_cli import entity_group
from science_tool.entity_kind_vocabulary import project_kind_vocabulary


def test_every_core_kind_is_reported() -> None:
    """Derivation, not transcription: the assertion is against the profile itself."""
    names = {row.name for row in project_kind_vocabulary(None)}
    assert {kind.name for kind in CORE_PROFILE.entity_kinds} <= names


def test_the_kinds_named_in_the_report_are_all_present() -> None:
    """The eleven the reporting project's enum was missing."""
    names = {row.name for row in project_kind_vocabulary(None)}
    missing = {
        "dataset", "theme", "plan", "topic", "concept", "book",
        "method", "report", "synthesis", "evidence-line", "spec",
    } - names
    assert not missing


def test_shipped_rows_are_labelled_shipped() -> None:
    assert {row.origin for row in project_kind_vocabulary(None)} == {"shipped"}


def _project(root: Path, *, local_kinds: list[dict]) -> None:
    (root / "science.yaml").write_text(
        "name: fixture\nprofile: research\nknowledge_profiles:\n  local: mylocal\n",
        encoding="utf-8",
    )
    manifest_dir = root / "knowledge" / "sources" / "mylocal"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "mylocal",
                "imports": ["core"],
                "strictness": "typed-extension",
                "entity_kinds": local_kinds,
                "relation_kinds": [],
            }
        ),
        encoding="utf-8",
    )


def test_project_local_kinds_are_reported_and_labelled(tmp_path: Path) -> None:
    _project(
        tmp_path,
        local_kinds=[
            {"name": "morphism-edge", "canonical_prefix": "morphism-edge", "layer": "layer/local",
             "description": "A project-local edge record."}
        ],
    )
    rows = {row.name: row.origin for row in project_kind_vocabulary(tmp_path)}
    assert rows["morphism-edge"] == "project"
    assert rows["dataset"] == "shipped"


def test_a_project_kind_shadowing_a_shipped_name_is_not_duplicated(tmp_path: Path) -> None:
    _project(
        tmp_path,
        local_kinds=[
            {"name": "dataset", "canonical_prefix": "dataset", "layer": "layer/local",
             "description": "Shadows a shipped kind."}
        ],
    )
    names = [row.name for row in project_kind_vocabulary(tmp_path)]
    assert names.count("dataset") == 1


def test_a_project_with_no_local_manifest_reports_the_shipped_vocabulary(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: fixture\nprofile: research\n", encoding="utf-8")
    assert {row.origin for row in project_kind_vocabulary(tmp_path)} == {"shipped"}


def test_rows_are_sorted_by_name() -> None:
    names = [row.name for row in project_kind_vocabulary(None)]
    assert names == sorted(names)


def test_cli_json_carries_a_flat_name_list_a_config_can_consume(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: fixture\nprofile: research\n", encoding="utf-8")
    with CliRunner().isolated_filesystem(temp_dir=tmp_path) as cwd:
        Path(cwd, "science.yaml").write_text("name: fixture\nprofile: research\n", encoding="utf-8")
        result = CliRunner().invoke(entity_group, ["kinds", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["meta"]["kinds"] == len(payload["rows"])
    assert "dataset" in payload["meta"]["names"]
