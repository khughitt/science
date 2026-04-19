from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as top_level_cli
from science_tool.refs_cli import refs_group

FIXTURE = Path(__file__).parent / "fixtures" / "refs" / "legacy_project"


def test_refs_group_exists_and_has_migrate_paper() -> None:
    runner = CliRunner()
    result = runner.invoke(refs_group, ["--help"])
    assert result.exit_code == 0
    assert "migrate-paper" in result.output


def test_top_level_cli_exposes_refs_group() -> None:
    runner = CliRunner()
    result = runner.invoke(top_level_cli, ["refs", "--help"])
    assert result.exit_code == 0
    assert "migrate-paper" in result.output


def test_migrate_paper_dry_run_does_not_write(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    before = (project / "doc" / "questions" / "q01-example.md").read_text()

    result = CliRunner().invoke(refs_group, ["migrate-paper", "--project-root", str(project)])
    assert result.exit_code == 0
    assert "Would rewrite" in result.output
    assert (project / "doc" / "questions" / "q01-example.md").read_text() == before


def test_migrate_paper_apply_rewrites_files(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    # Fixture isn't a git repo: --apply should proceed without --force.
    result = CliRunner().invoke(refs_group, ["migrate-paper", "--project-root", str(project), "--apply"])
    assert result.exit_code == 0, result.output
    assert "Rewrote" in result.output

    text = (project / "doc" / "questions" / "q01-example.md").read_text()
    assert "article:" not in text
    assert "paper:Smith2024" in text


def test_migrate_paper_idempotent(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    runner = CliRunner()
    runner.invoke(refs_group, ["migrate-paper", "--project-root", str(project), "--apply"])
    result = runner.invoke(refs_group, ["migrate-paper", "--project-root", str(project), "--apply"])
    assert result.exit_code == 0
    assert "No `article:` references found" in result.output


def test_migrate_paper_blocks_when_dirty(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"],
        cwd=project,
        check=True,
    )
    # No commit: working tree is dirty (all files untracked).
    result = CliRunner().invoke(
        refs_group, ["migrate-paper", "--project-root", str(project), "--apply"]
    )
    assert result.exit_code != 0
    assert "not clean" in result.output.lower()
