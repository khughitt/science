from __future__ import annotations

from click.testing import CliRunner

from science_tool.cli import main


def test_curate_group_registered() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["curate", "--help"])
    assert result.exit_code == 0
    assert "inventory" in result.output
