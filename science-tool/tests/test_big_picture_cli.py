from __future__ import annotations

from click.testing import CliRunner

from science_tool.cli import main


def test_big_picture_group_registered() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["big-picture", "--help"])
    assert result.exit_code == 0
    assert "resolve-questions" in result.output
    assert "validate" in result.output
