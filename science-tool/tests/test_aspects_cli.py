from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def _seed_legacy_project(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] Pipeline\n- type: dev\n- priority: P2\n- status: proposed\n- created: 2026-04-01\n\nBody.\n"
    )
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\naspects: [hypothesis-testing, software-development]\n"
    )


def test_migrate_group_registered() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["aspects", "--help"])
    assert result.exit_code == 0
    assert "migrate" in result.output


def test_migrate_dry_run_prints_plan_without_writing(tmp_path: Path) -> None:
    _seed_legacy_project(tmp_path)
    original = (tmp_path / "tasks" / "active.md").read_text()
    runner = CliRunner()
    result = runner.invoke(main, ["aspects", "migrate", "--project-root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "t001" in result.output
    assert (tmp_path / "tasks" / "active.md").read_text() == original


def test_migrate_apply_rewrites_file(tmp_path: Path) -> None:
    _seed_legacy_project(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["aspects", "migrate", "--project-root", str(tmp_path), "--apply"])
    assert result.exit_code == 0, result.output
    body = (tmp_path / "tasks" / "active.md").read_text()
    assert "- type: dev" not in body
    assert "- aspects: [software-development]" in body
