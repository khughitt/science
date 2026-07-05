"""CLI tests for `commons promote topic`."""

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


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    proj = tmp_path / "proj-alpha"
    shutil.copytree(FIXTURES / "proj-alpha", proj)
    _init_repo(proj)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(proj), "commit", "-q", "-m", "init"],
        check=True,
        capture_output=True,
    )

    commons = tmp_path / "commons"
    commons.mkdir()
    (commons / "topics").mkdir()
    (commons / ".migrations").mkdir()
    _init_repo(commons)
    subprocess.run(
        ["git", "-C", str(commons), "commit", "--allow-empty", "-q", "-m", "init"],
        check=True,
        capture_output=True,
    )
    return proj, commons


def test_cli_promote_topic_dry_run_lists_candidates(tmp_path, monkeypatch) -> None:
    from science_tool.commons import cli as commons_cli

    proj, commons = _setup(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
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
        ["promote", "topic", "--from", "proj-alpha"],
    )

    assert result.exit_code == 0, result.output
    assert "single-instance" in result.output
    assert "flatten-source" not in result.output


def test_cli_promote_topic_single_entity_form(tmp_path, monkeypatch) -> None:
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
        ["promote", "topic", "topic:single-instance", "--from", "proj-alpha"],
    )

    assert result.exit_code == 0, result.output
    assert "single-instance" in result.output


def test_cli_promote_topic_rejects_wrong_id_prefix(tmp_path, monkeypatch) -> None:
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
        ["promote", "topic", "paper:Foo", "--from", "proj-alpha"],
    )

    assert result.exit_code != 0
    assert "topic:" in result.output


def test_cli_promote_topic_apply_writes_commons_and_rewrites_overlay(
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
            "topic",
            "topic:single-instance",
            "--from",
            "proj-alpha",
            "--apply",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (commons / "topics" / "single-instance.md").exists()
    overlay = (proj / "overlays" / "topics" / "single-instance.md").read_text(
        encoding="utf-8",
    )
    assert "overlay_of: topic:single-instance" in overlay
