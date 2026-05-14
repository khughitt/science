"""Tests for science_tool.commons.cli."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.commons.cli import commons_group


def test_init_creates_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "commons"))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["init"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "commons" / "datasets").is_dir()
    assert (tmp_path / "commons" / ".git").is_dir()


def test_init_force_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "commons"
    root.mkdir()
    (root / "stray.txt").write_text("hi")
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["init", "--force"])
    assert result.exit_code == 0, result.output
    assert (root / "datasets").is_dir()


def test_index_rebuild_with_valid_fixtures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil
    fixtures = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(fixtures, root)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["index", "rebuild"])
    assert result.exit_code == 0, result.output
    assert "indexed 5" in result.output
    assert (root / "registry.sqlite").is_file()


def test_index_rebuild_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil
    fixtures = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(fixtures, root)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["index", "rebuild", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["entities_indexed"] == 5
    assert payload["errors"] == []
    assert payload["duration_ms"] >= 0


def test_index_rebuild_exit_1_when_entity_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil
    fixtures = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(fixtures, root)
    # Drop in a bad paper. bibkey "bad-name" (hyphen) violates the paper-mixin
    # bibkey regex while filename/id/type stay mutually consistent.
    (root / "papers" / "badname.md").write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+paper/1.0"\n'
        'id: "paper:badname"\n'
        'type: "paper"\n'
        'title: "Bad"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        'bibkey: "bad-name"\n'
        'authors: ["X"]\n'
        "year: 2025\n"
        'journal: "T"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["index", "rebuild"])
    assert result.exit_code == 1


def test_missing_store_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "nope"))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["index", "rebuild"])
    assert result.exit_code == 1
    assert "commons store not found" in result.output
