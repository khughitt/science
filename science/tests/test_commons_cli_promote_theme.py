"""CLI tests for `commons promote theme`."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from click.testing import CliRunner

FIXTURES = Path(__file__).parent / "fixtures" / "promote"


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@x"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "test"],
        check=True,
        capture_output=True,
    )


def _copy_project(tmp_path: Path, fixture_name: str) -> Path:
    proj = tmp_path / fixture_name
    shutil.copytree(FIXTURES / fixture_name, proj)
    invalid_theme = proj / "entities" / "themes" / "cross-biological.md"
    if invalid_theme.exists():
        invalid_theme.unlink()
    _init_repo(proj)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(proj), "commit", "-q", "-m", "init"],
        check=True,
        capture_output=True,
    )
    return proj


def _create_commons(tmp_path: Path) -> Path:
    commons = tmp_path / "commons"
    commons.mkdir()
    (commons / "themes").mkdir()
    (commons / ".migrations").mkdir()
    _init_repo(commons)
    subprocess.run(
        ["git", "-C", str(commons), "commit", "--allow-empty", "-q", "-m", "init"],
        check=True,
        capture_output=True,
    )
    return commons


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    proj = _copy_project(tmp_path, "proj-alpha")
    commons = _create_commons(tmp_path)
    return proj, commons


def test_cli_promote_theme_dry_run_excludes_project_scope(tmp_path, monkeypatch) -> None:
    from science_tool.commons import cli as commons_cli

    alpha = _copy_project(tmp_path, "proj-alpha")
    beta = _copy_project(tmp_path, "proj-beta")
    commons = _create_commons(tmp_path)
    projects = {"proj-alpha": alpha, "proj-beta": beta}
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: projects[slug],
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.prompt_resolve",
        lambda conflict: sorted(conflict.candidates.items())[0][1],
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: commons,
    )

    runner = CliRunner()
    result = runner.invoke(
        commons_cli.commons_group,
        ["promote", "theme", "--from", "proj-alpha", "--from", "proj-beta"],
    )

    assert result.exit_code == 0, result.output
    assert "cross-no-conflict" in result.output
    assert "cross-conflict" in result.output
    assert "project-scope" not in result.output


def test_cli_promote_theme_single_entity_apply_writes_commons(
    tmp_path,
    monkeypatch,
) -> None:
    from science_tool.commons import cli as commons_cli

    proj, commons = _setup(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: commons,
    )

    runner = CliRunner()
    result = runner.invoke(
        commons_cli.commons_group,
        [
            "promote",
            "theme",
            "theme:cross-no-conflict",
            "--from",
            "proj-alpha",
            "--apply",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (commons / "themes" / "cross-no-conflict.md").exists()


def test_cli_promote_theme_rejects_wrong_id_prefix(tmp_path, monkeypatch) -> None:
    from science_tool.commons import cli as commons_cli

    proj, commons = _setup(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: commons,
    )

    runner = CliRunner()
    result = runner.invoke(
        commons_cli.commons_group,
        ["promote", "theme", "paper:Foo", "--from", "proj-alpha"],
    )

    assert result.exit_code != 0
    assert "theme:" in result.output
