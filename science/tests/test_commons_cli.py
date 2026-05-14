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


def _seeded_store(tmp_path: Path) -> Path:
    import shutil
    fixtures = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(fixtures, root)
    return root


def test_show_human(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(commons_group, ["show", "paper:Adams2025"])
    assert result.exit_code == 0, result.output
    assert "paper:Adams2025" in result.output
    assert "Adams, A." in result.output  # author from frontmatter


def test_show_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(commons_group, ["show", "paper:Adams2025", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["canonical_id"] == "paper:Adams2025"
    assert payload["frontmatter"]["bibkey"] == "Adams2025"
    assert "commons_metadata" in payload


def test_show_rejects_project_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(
        commons_group, ["show", "paper:Adams2025", "--project", "foo"]
    )
    assert result.exit_code == 1
    assert "Phase D" in result.output


def test_show_missing_entity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(commons_group, ["show", "paper:DoesNotExist"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower() or "failed" in result.output.lower()


def test_find_default_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(commons_group, ["find", "dataset"])
    assert result.exit_code == 0
    assert "dataset:cath-domains" in result.output
    assert "dataset:rnaseq-example" in result.output


def test_find_with_tag_and(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(
        commons_group, ["find", "dataset", "--tag", "rnaseq", "--tag", "bulk"]
    )
    assert result.exit_code == 0
    assert "dataset:rnaseq-example" in result.output
    assert "dataset:cath-domains" not in result.output


def test_find_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(commons_group, ["find", "paper", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert isinstance(payload, list)
    assert payload[0]["canonical_id"] == "paper:Adams2025"


def test_find_year_filter_only_for_papers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(
        commons_group, ["find", "dataset", "--year-from", "2020"]
    )
    assert result.exit_code != 0


def test_show_before_rebuild_exits_1_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Show must surface CommonsRegistryError as a clean exit-1 message,
    not a raw sqlite3.OperationalError traceback."""
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    # Note: no `index rebuild` invocation — registry.sqlite is absent.
    runner = CliRunner()
    result = runner.invoke(commons_group, ["show", "paper:Adams2025"])
    assert result.exit_code == 1
    assert "OperationalError" not in result.output
    assert (
        "registry" in result.output.lower()
        or "index rebuild" in result.output
    )


def test_validate_clean_store_exits_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["validate"])
    assert result.exit_code == 0, result.output
    assert "checked 5 entities" in result.output


def test_validate_reports_per_entity_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    # bibkey "bad-name" (hyphen) violates the paper-mixin bibkey regex.
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
    result = runner.invoke(commons_group, ["validate"])
    assert result.exit_code == 1
    assert "badname.md" in result.output


def test_validate_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["validate", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["checked"] == 5
    assert payload["errors"] == []


def test_find_before_rebuild_exits_1_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["find", "paper"])
    assert result.exit_code == 1
    assert "OperationalError" not in result.output
    assert (
        "registry" in result.output.lower()
        or "index rebuild" in result.output
    )
