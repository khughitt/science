from click.testing import CliRunner

from science_tool.cli import main


def test_skills_lint_help_exits_zero() -> None:
    result = CliRunner().invoke(main, ["skills", "lint", "--help"])
    assert result.exit_code == 0
    assert "lint" in result.output.lower()
