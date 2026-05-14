"""Verify `science commons` is reachable from the top-level CLI."""
from __future__ import annotations

from click.testing import CliRunner

from science_tool.cli import main


def test_commons_subcommand_listed_in_main_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "commons" in result.output


def test_commons_help_runs() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["commons", "--help"])
    assert result.exit_code == 0
    assert "init" in result.output
    assert "show" in result.output
    assert "find" in result.output
    assert "validate" in result.output


def test_commons_index_help_runs() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["commons", "index", "--help"])
    assert result.exit_code == 0
    assert "rebuild" in result.output
