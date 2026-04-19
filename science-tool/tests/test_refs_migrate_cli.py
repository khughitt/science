from __future__ import annotations

from click.testing import CliRunner

from science_tool.cli import main as top_level_cli
from science_tool.refs_cli import refs_group


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
